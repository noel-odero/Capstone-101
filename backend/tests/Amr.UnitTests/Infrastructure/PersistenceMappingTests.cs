using System.Text.Json;
using System.Text.Json.Nodes;
using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Services;
using Amr.Domain.Enums;
using Amr.Infrastructure.Persistence;
using Amr.Infrastructure.Persistence.Entities;

namespace Amr.UnitTests.Infrastructure;

/// <summary>Entity mapping without a database: what is written is exactly what is read back, in order.</summary>
public class RunEntityMapperTests
{
    private static readonly DateTimeOffset Now = new(2026, 10, 15, 12, 0, 0, TimeSpan.Zero);

    private static readonly JsonSerializerOptions PublicJson = CreatePublicJson();

    private static JsonSerializerOptions CreatePublicJson()
    {
        var options = new JsonSerializerOptions();
        Amr.Api.Configuration.ApiJsonOptions.Configure(options);
        return options;
    }

    private static async Task<SimulationDto> SimulationAsync(string fixture, CreateSimulationRequest request) =>
        await new SimulationService(ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Fixture(fixture))), new FakeRunRepository()).RunAsync(request, CancellationToken.None);

    private static async Task<ComparisonDto> ComparisonAsync() =>
        await new ComparisonService(ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Fixture("compare_200"))), new FakeRunRepository())
            .RunAsync(new() { ResistanceProfile = [0, 1, 0, 0, 0, 0, 0], EnvironmentSeed = 100001, PolicySeed = 900001 }, CancellationToken.None);

    private static ExperimentRun Stored(ExperimentRun run, ModelProvenanceDto provenance)
    {
        run.ModelVersion = RunEntityMapper.ToEntity(provenance, Now);
        return run;
    }

    private static void AssertSameJson<T>(T expected, T actual) =>
        Assert.True(
            JsonNode.DeepEquals(JsonSerializer.SerializeToNode(expected, PublicJson), JsonSerializer.SerializeToNode(actual, PublicJson)),
            $"{JsonSerializer.Serialize(expected, PublicJson)}{Environment.NewLine}{JsonSerializer.Serialize(actual, PublicJson)}");

    [Theory]
    [InlineData("simulate_200_ppo", StrategyKind.Ppo, 100001L, null)]
    [InlineData("simulate_200_baseline", StrategyKind.RandomSusceptibleBaseline, 100001L, 900001L)]
    public async Task A_simulation_survives_the_entity_round_trip_unchanged(string fixture, StrategyKind strategy, long seed, long? policySeed)
    {
        var simulation = await SimulationAsync(fixture, new() { ResistanceProfile = [0, 1, 0, 0, 0, 0, 0], Strategy = strategy, EnvironmentSeed = seed, PolicySeed = policySeed });

        var entity = Stored(RunEntityMapper.ToEntity(simulation, Guid.NewGuid(), Now), simulation.Provenance);
        var restored = RunEntityMapper.ToSimulationDto(entity);

        AssertSameJson(simulation with { IsPersisted = true }, restored);
    }

    [Fact]
    public async Task A_terminal_simulation_with_no_steps_round_trips()
    {
        var simulation = await SimulationAsync("simulate_200_terminal", new() { ResistanceProfile = [1, 1, 1, 1, 1, 1, 1], Strategy = StrategyKind.Ppo, EnvironmentSeed = 1 });

        var entity = Stored(RunEntityMapper.ToEntity(simulation, Guid.NewGuid(), Now), simulation.Provenance);

        Assert.Empty(entity.StrategyRuns.Single().StepTraces);
        AssertSameJson(simulation with { IsPersisted = true }, RunEntityMapper.ToSimulationDto(entity));
    }

    [Fact]
    public async Task A_comparison_round_trips_with_both_strategies_the_contract_and_the_caveat()
    {
        var comparison = await ComparisonAsync();

        var entity = Stored(RunEntityMapper.ToEntity(comparison, Guid.NewGuid(), Now), comparison.Provenance);
        var restored = RunEntityMapper.ToComparisonDto(entity);

        AssertSameJson(comparison with { IsPersisted = true }, restored);
        Assert.Equal(2, entity.StrategyRuns.Count);
    }

    [Fact]
    public async Task Steps_are_restored_in_step_order_whatever_order_the_rows_come_back_in()
    {
        var simulation = await SimulationAsync("simulate_200_ppo", new() { ResistanceProfile = [0, 1, 0, 0, 0, 0, 0], Strategy = StrategyKind.Ppo, EnvironmentSeed = 100001 });
        var entity = Stored(RunEntityMapper.ToEntity(simulation, Guid.NewGuid(), Now), simulation.Provenance);
        entity.StrategyRuns.Single().StepTraces.Reverse();

        var restored = RunEntityMapper.ToSimulationDto(entity);

        Assert.Equal(Enumerable.Range(0, simulation.Result!.Steps.Count), restored.Result!.Steps.Select(step => step.StepIndex));
    }

    [Fact]
    public async Task The_support_flag_and_the_susceptibility_flag_are_stored_separately()
    {
        var simulation = await SimulationAsync("simulate_200_ppo", new() { ResistanceProfile = [0, 1, 0, 0, 0, 0, 0], Strategy = StrategyKind.Ppo, EnvironmentSeed = 100001 });

        var rows = RunEntityMapper.ToEntity(simulation, Guid.NewGuid(), Now).StrategyRuns.Single().StepTraces;

        var unsupported = rows.Where(step => step.TransitionStatus == "unsupported_no_candidate").ToList();
        Assert.NotEmpty(unsupported);
        Assert.All(unsupported, step =>
        {
            Assert.True(step.SelectedDrugSusceptible);
            Assert.False(step.HasCandidateTransition);
            Assert.Null(step.SelectedOutcome);
        });
        Assert.Equal(simulation.Result!.Metrics.UnsupportedStepCount, unsupported.Count);
    }

    [Fact]
    public async Task Only_completed_results_can_be_mapped_for_storage()
    {
        var simulation = await SimulationAsync("simulate_200_ppo", new() { ResistanceProfile = [0, 1, 0, 0, 0, 0, 0], Strategy = StrategyKind.Ppo, EnvironmentSeed = 100001 });
        var comparison = await ComparisonAsync();

        Assert.Throws<InvalidOperationException>(() => RunEntityMapper.ToEntity(simulation with { Result = null }, Guid.NewGuid(), Now));
        Assert.Throws<InvalidOperationException>(() => RunEntityMapper.ToEntity(comparison with { Contract = null }, Guid.NewGuid(), Now));
        Assert.Throws<InvalidOperationException>(() => RunEntityMapper.ToEntity(comparison with { Baseline = null }, Guid.NewGuid(), Now));
    }

    [Fact]
    public async Task The_experiment_run_carries_the_inputs_provenance_and_seed_configuration()
    {
        var comparison = await ComparisonAsync();

        var run = RunEntityMapper.ToEntity(comparison, Guid.NewGuid(), Now);

        Assert.Equal((ExperimentKind.Comparison, RunStatus.Completed), (run.Kind, run.Status));
        Assert.Equal(new[] { 0, 1, 0, 0, 0, 0, 0 }, run.InitialProfile);
        Assert.Equal((100001L, "client", 900001L, "client"), (run.EnvironmentSeed, run.EnvironmentSeedSource, run.PolicySeed, run.PolicySeedSource));
        Assert.Equal(comparison.Provenance.ServiceVersion, run.ServiceVersion);
        Assert.Equal(Now, run.RecordedAtUtc);
        Assert.Equal(comparison.CreatedAtUtc, run.CreatedAtUtc);
    }
}

public class ModelVersionFingerprintTests
{
    private static ModelProvenanceDto Provenance(Action<Dictionary<string, JsonElement>>? reward = null, string checkpoint = "d10c26185c9903d96d0f2003643b76be6df4f03c39e0d2e5f7945e763b7d9093", string service = "0.1.0")
    {
        var spec = new Dictionary<string, JsonElement>
        {
            ["objective"] = JsonSerializer.SerializeToElement("normalized_resistance_burden"),
            ["normalization"] = JsonSerializer.SerializeToElement(7),
            ["terminal_convention"] = JsonSerializer.SerializeToElement("all_resistant_state_persists_to_horizon"),
        };
        reward?.Invoke(spec);
        return new ModelProvenanceDto(
            "ppo_seed_12000", "MaskablePPO", checkpoint, "7a5e3e1fe730676a0793674e4ff4aaf3c6ce1177ad5588eed4bb2e5d627edb44",
            "REF_UNIFORM_SUPPORTED", 8, spec, "susceptible_actions_only", ["A", "B", "C", "D", "E", "F", "G"], service);
    }

    [Fact]
    public void The_fingerprint_is_a_lowercase_sha256_hex_string()
    {
        Assert.Matches("^[0-9a-f]{64}$", ModelVersionFingerprint.Compute(Provenance()));
    }

    [Fact]
    public void The_same_configuration_hashes_the_same_regardless_of_reward_key_order_or_service_version()
    {
        var reordered = Provenance(spec =>
        {
            var entries = spec.ToList();
            spec.Clear();
            foreach (var (key, value) in entries.AsEnumerable().Reverse())
            {
                spec[key] = value;
            }
        });

        Assert.Equal(ModelVersionFingerprint.Compute(Provenance()), ModelVersionFingerprint.Compute(reordered));
        Assert.Equal(ModelVersionFingerprint.Compute(Provenance()), ModelVersionFingerprint.Compute(Provenance(service: "9.9.9")));
    }

    [Fact]
    public void Any_change_to_the_checkpoint_or_the_reward_specification_changes_the_fingerprint()
    {
        var baseline = ModelVersionFingerprint.Compute(Provenance());

        Assert.NotEqual(baseline, ModelVersionFingerprint.Compute(Provenance(checkpoint: new string('a', 64))));
        Assert.NotEqual(baseline, ModelVersionFingerprint.Compute(Provenance(spec => spec["normalization"] = JsonSerializer.SerializeToElement(8))));
        Assert.NotEqual(baseline, ModelVersionFingerprint.Compute(Provenance(spec => spec["new_key"] = JsonSerializer.SerializeToElement(1))));
    }
}
