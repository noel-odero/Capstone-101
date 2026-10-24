using System.ComponentModel.DataAnnotations;
using Amr.Application.DTOs.Analyses;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Persistence;
using Amr.Application.Services;
using Amr.Domain.Enums;

namespace Amr.UnitTests.Application.Services;

public class AnalysisComparisonServiceTests
{
    private static async Task<SavedAnalysisDto> Record()
    {
        var handler = StubHandler.Returning(() => PythonFixtures.Fixture("compare_200"));
        var run = await new ComparisonService(ClientFactory.Create(handler), new FakeRunRepository())
            .RunAsync(new() { ResistanceProfile = [0, 1, 0, 0, 0, 0, 0], EnvironmentSeed = 100001, PolicySeed = 900001 }, CancellationToken.None);
        return new(run.Id, ExperimentKind.Comparison, run.CreatedAtUtc, run.Ppo!.InitialProfile,
            run.Provenance, run.SeedConfiguration, [run.Ppo, run.Dqn!, run.Baseline!], run.MetricDefinitions, run.Contract!.Verified, null);
    }

    private sealed class SavedRepository(params SavedAnalysisDto[] records) : IAnalysisRepository
    {
        public Task<IReadOnlyList<SavedAnalysisDto>> FindManyAsync(IReadOnlyCollection<Guid> ids, CancellationToken cancellationToken) =>
            Task.FromResult<IReadOnlyList<SavedAnalysisDto>>(records.Where(run => ids.Contains(run.Id)).ToArray());
    }

    private static Task<AnalysisComparisonDto> Compare(params SavedAnalysisDto[] records) =>
        new AnalysisComparisonService(new SavedRepository(records)).CompareAsync(new() { AnalysisIds = records.Select(run => run.Id).ToArray() }, CancellationToken.None);

    [Fact]
    public async Task Missing_DQN_is_unavailable_and_zero_burden_is_preserved()
    {
        var first = await Record();
        var second = first with { Id = Guid.NewGuid(), Strategies = first.Strategies.Where(result => result.Strategy != StrategyKind.Dqn).ToArray() };
        first = first with { Strategies = first.Strategies.Select(result => result with { Metrics = result.Metrics with { CumulativeResistanceBurden = 0 } }).ToArray() };
        var result = await Compare(first, second);
        Assert.Equal(0d, result.BurdenDifferences[0].PpoMinusDqn);
        Assert.Null(result.BurdenDifferences[1].PpoMinusDqn);
        Assert.Null(result.BurdenDifferences[1].DqnMinusBaseline);
        Assert.NotNull(result.BurdenDifferences[1].PpoMinusBaseline);
        Assert.Contains(result.Compatibility.Issues, issue => issue.Code == "dqn_unavailable");
        Assert.DoesNotContain(result.Analyses[1].Strategies, strategy => strategy.Strategy == StrategyKind.Dqn);
    }

    [Fact]
    public async Task Changed_data_checkpoints_and_metric_definitions_prevent_pooling()
    {
        var first = await Record();
        var definitions = first.MetricDefinitions.ToDictionary();
        definitions["cumulativeResistanceBurden"] = definitions["cumulativeResistanceBurden"] with { Unit = "changed-unit" };
        var second = first with {
            Id = Guid.NewGuid(), MetricDefinitions = definitions,
            Provenance = first.Provenance with { InteractionDataSha256 = new string('a', 64), Horizon = 4 },
            Strategies = first.Strategies.Select(result => result.Strategy == StrategyKind.Dqn
                ? result with { Model = result.Model! with { CheckpointSha256 = new string('b', 64) } } : result).ToArray(),
        };
        var result = await Compare(first, second);
        Assert.Equal("incompatible", result.Compatibility.Status);
        foreach (var code in new[] { "environment_changed", "evaluation_changed", "checkpoint_changed", "metric_definitions_changed" })
            Assert.Contains(result.Compatibility.Issues, issue => issue.Code == code);
        Assert.Contains("No pooled performance statistic", result.Interpretation);
    }

    [Fact]
    public async Task Matching_fields_and_reordered_reward_keys_do_not_invent_incompatibility()
    {
        var first = await Record();
        var second = first with {
            Id = Guid.NewGuid(), SeedConfiguration = first.SeedConfiguration with { EnvironmentSeed = 123456 },
            Provenance = first.Provenance with { RewardSpecification = first.Provenance.RewardSpecification.Reverse().ToDictionary() },
        };
        var result = await Compare(first, second);
        Assert.Equal("exploratory", result.Compatibility.Status);
        Assert.DoesNotContain(result.Compatibility.Issues, issue => issue.Code is "evaluation_changed" or "metric_definitions_changed");
        Assert.Contains(result.Compatibility.Issues, issue => issue.Code == "different_seeds");
        Assert.Equal(first.Strategies, result.Analyses[0].Strategies);
    }

    [Fact]
    public async Task Replays_are_not_independent_samples_and_unknown_legacy_identity_is_explicit()
    {
        var first = await Record();
        var replay = first with { Id = Guid.NewGuid() };
        Assert.Contains((await Compare(first, replay)).Compatibility.Issues, issue => issue.Code == "shared_random_draws");
        var unknown = replay with { Provenance = replay.Provenance with { InteractionDataSha256 = "unknown" }, ComparisonVerified = null };
        var result = await Compare(first, unknown);
        Assert.Equal("incompatible", result.Compatibility.Status);
        Assert.Contains(result.Compatibility.Issues, issue => issue.Code == "provenance_unknown");
        Assert.Contains(result.Compatibility.Issues, issue => issue.Code == "pairing_unverified");
    }

    [Fact]
    public async Task Unavailable_records_fail_as_a_set_and_selection_order_is_preserved()
    {
        var first = await Record();
        var second = first with { Id = Guid.NewGuid() };
        var service = new AnalysisComparisonService(new SavedRepository(first, second));
        var result = await service.CompareAsync(new() { AnalysisIds = [second.Id, first.Id] }, CancellationToken.None);
        Assert.Equal(new[] { second.Id, first.Id }, result.Analyses.Select(run => run.Id));
        var error = await Assert.ThrowsAsync<AmrException>(() => service.CompareAsync(new() { AnalysisIds = [first.Id, Guid.NewGuid()] }, CancellationToken.None));
        Assert.Equal(ErrorCategory.NotFound, error.Category);
        Assert.Equal("analysis_not_found", error.Code);
    }

    [Fact]
    public async Task Selection_is_bounded_unique_and_nonempty()
    {
        var service = new AnalysisComparisonService(new SavedRepository());
        var id = Guid.NewGuid();
        foreach (var ids in new[] { Array.Empty<Guid>(), new[] { id }, new[] { id, id }, new[] { id, Guid.Empty }, Enumerable.Range(0, 51).Select(_ => Guid.NewGuid()).ToArray() })
            await Assert.ThrowsAsync<ValidationException>(() => service.CompareAsync(new() { AnalysisIds = ids }, CancellationToken.None));
    }
}
