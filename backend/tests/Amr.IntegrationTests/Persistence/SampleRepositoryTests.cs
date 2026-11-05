using Amr.Application.DTOs.Samples;
using Amr.Application.Errors;
using Amr.Infrastructure.Persistence;
using Amr.IntegrationTests.Infrastructure;
using Amr.TestSupport;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.EntityFrameworkCore;
using System.Text.Json;

namespace Amr.IntegrationTests.Persistence;

public class SampleRepositoryTests(PostgresDatabaseFixture db) : IClassFixture<PostgresDatabaseFixture>
{
    [PostgresFact]
    public async Task Concurrent_case_and_space_variants_are_rejected_but_other_owners_can_reuse_a_label()
    {
        var owner = Guid.NewGuid().ToString();
        async Task<AmrException?> Create(string label)
        {
            await using var context = db.CreateContext();
            try
            {
                await new SampleRepository(context, new FixedCurrentUser(owner), TimeProvider.System)
                    .CreateAsync(new CreateSampleRequest { Label = label, ResistanceProfile = [0, 0, 0, 0, 0, 0, 0] }, CancellationToken.None);
                return null;
            }
            catch (AmrException exception) { return exception; }
        }

        var results = await Task.WhenAll(Create("  UTI-024  "), Create("uti-024"));
        Assert.Single(results, result => result is null);
        Assert.Equal("sample_label_exists", Assert.Single(results, result => result is not null)!.Code);
        await using var read = db.CreateContext();
        Assert.Single(await new SampleRepository(read, new FixedCurrentUser(owner), TimeProvider.System).ListAsync(CancellationToken.None));
        var other = await new SampleRepository(read, new FixedCurrentUser("other:" + owner), TimeProvider.System)
            .CreateAsync(new CreateSampleRequest { Label = "UTI-024", ResistanceProfile = [0, 0, 0, 0, 0, 0, 0] }, CancellationToken.None);
        Assert.Equal("UTI-024", other.Label);
    }

    [PostgresFact]
    public async Task Deleting_an_analyzed_sample_preserves_its_comparison_and_all_step_traces()
    {
        var owner = Guid.NewGuid().ToString();
        var comparison = await SampleDtos.Comparison();
        await using var context = db.CreateContext();
        var samples = new SampleRepository(context, new FixedCurrentUser(owner), TimeProvider.System);
        var sample = await samples.CreateAsync(new CreateSampleRequest { Label = "UTI-024", ResistanceProfile = comparison.Ppo!.InitialProfile }, CancellationToken.None);
        var runs = new RunRepository(context, TimeProvider.System, new FixedCurrentUser(owner), NullLogger<RunRepository>.Instance);
        var run = comparison with { Id = Guid.NewGuid(), SampleId = sample.Id };
        await runs.SaveComparisonAsync(run, CancellationToken.None);
        var before = await runs.FindComparisonAsync(run.Id, CancellationToken.None);
        var traceCount = await context.StepTraces.CountAsync();

        Assert.True(await samples.DeleteAsync(sample.Id, CancellationToken.None));

        await using var read = db.CreateContext();
        Assert.Null(await new SampleRepository(read, new FixedCurrentUser(owner), TimeProvider.System).FindAsync(sample.Id, CancellationToken.None));
        var stored = await new RunRepository(read, TimeProvider.System, new FixedCurrentUser(owner), NullLogger<RunRepository>.Instance).FindComparisonAsync(run.Id, CancellationToken.None);
        Assert.NotNull(stored);
        Assert.Null(stored.SampleId);
        Assert.Equal(JsonSerializer.Serialize(before!.Ppo), JsonSerializer.Serialize(stored.Ppo));
        Assert.Equal(JsonSerializer.Serialize(before.Baseline), JsonSerializer.Serialize(stored.Baseline));
        Assert.Equal(JsonSerializer.Serialize(before.Dqn), JsonSerializer.Serialize(stored.Dqn));
        Assert.Equal(traceCount, await read.StepTraces.CountAsync());
        await new SampleRepository(read, new FixedCurrentUser(owner), TimeProvider.System)
            .CreateAsync(new CreateSampleRequest { Label = sample.Label, ResistanceProfile = sample.ResistanceProfile }, CancellationToken.None);
    }

    [PostgresFact]
    public async Task Only_the_owner_can_delete_a_sample_and_missing_samples_return_false()
    {
        var owner = Guid.NewGuid().ToString();
        await using var context = db.CreateContext();
        var samples = new SampleRepository(context, new FixedCurrentUser(owner), TimeProvider.System);
        var sample = await samples.CreateAsync(new CreateSampleRequest { Label = "Private", ResistanceProfile = [0, 0, 0, 0, 0, 0, 0] }, CancellationToken.None);
        var other = new SampleRepository(context, new FixedCurrentUser("other:" + owner), TimeProvider.System);
        Assert.False(await other.DeleteAsync(sample.Id, CancellationToken.None));
        Assert.NotNull(await samples.FindAsync(sample.Id, CancellationToken.None));
        Assert.True(await samples.DeleteAsync(sample.Id, CancellationToken.None));
        Assert.False(await samples.DeleteAsync(sample.Id, CancellationToken.None));
    }

    [PostgresFact]
    public async Task Saved_samples_survive_new_contexts_and_are_private_to_their_owner()
    {
        var owner = Guid.NewGuid().ToString();
        SampleDto first;
        SampleDto second;
        await using (var context = db.CreateContext())
        {
            var samples = new SampleRepository(context, new FixedCurrentUser(owner), TimeProvider.System);
            first = await samples.CreateAsync(new CreateSampleRequest { Label = "  Sample A  ", ResistanceProfile = [0, 1, 0, 0, 0, 0, 0] }, CancellationToken.None);
            second = await samples.CreateAsync(new CreateSampleRequest { Label = "Sample B", ResistanceProfile = [1, 0, 0, 0, 0, 0, 0] }, CancellationToken.None);
        }
        await using var read = db.CreateContext();
        var saved = await new SampleRepository(read, new FixedCurrentUser(owner), TimeProvider.System).ListAsync(CancellationToken.None);
        Assert.Equal(2, saved.Count);
        Assert.Equal("Sample A", saved.Single(sample => sample.Id == first.Id).Label);
        Assert.Equal(second.ResistanceProfile, saved.Single(sample => sample.Id == second.Id).ResistanceProfile);
        Assert.All(saved, sample => Assert.Empty(sample.Runs));
        Assert.All(saved, sample => Assert.NotEqual(default, sample.AddedAtUtc));
        var other = new SampleRepository(read, new FixedCurrentUser("other:" + owner), TimeProvider.System);
        Assert.Null(await other.FindAsync(first.Id, CancellationToken.None));
        Assert.Empty(await other.ListAsync(CancellationToken.None));
    }

    [PostgresFact]
    public async Task Saved_comparisons_link_atomically_and_reruns_keep_the_sample_profile()
    {
        var owner = Guid.NewGuid().ToString();
        var comparison = await SampleDtos.Comparison();
        SampleDto sample;
        await using (var context = db.CreateContext())
        {
            sample = await new SampleRepository(context, new FixedCurrentUser(owner), TimeProvider.System).CreateAsync(new CreateSampleRequest { Label = "UTI-024", ResistanceProfile = comparison.Ppo!.InitialProfile }, CancellationToken.None);
        }
        for (var index = 0; index < 2; index++)
        {
            await using var context = db.CreateContext();
            var runs = new RunRepository(context, TimeProvider.System, new FixedCurrentUser(owner), NullLogger<RunRepository>.Instance);
            var run = comparison with { Id = Guid.NewGuid(), SampleId = sample.Id };
            await runs.SaveComparisonAsync(run, CancellationToken.None);
            Assert.Equal(sample.Id, (await runs.FindComparisonAsync(run.Id, CancellationToken.None))!.SampleId);
        }
        await using var read = db.CreateContext();
        var saved = await new SampleRepository(read, new FixedCurrentUser(owner), TimeProvider.System).FindAsync(sample.Id, CancellationToken.None);
        Assert.NotNull(saved);
        Assert.Equal(2, saved.Runs.Count);
        Assert.Equal(sample.ResistanceProfile, saved.ResistanceProfile);
    }

    [PostgresFact]
    public async Task Wrong_owner_and_changed_profiles_cannot_link_a_run_or_mark_a_sample_as_run()
    {
        var owner = Guid.NewGuid().ToString();
        var comparison = await SampleDtos.Comparison();
        SampleDto sample;
        await using (var context = db.CreateContext())
        {
            sample = await new SampleRepository(context, new FixedCurrentUser(owner), TimeProvider.System).CreateAsync(new CreateSampleRequest { Label = "Private", ResistanceProfile = comparison.Ppo!.InitialProfile }, CancellationToken.None);
        }
        await using (var context = db.CreateContext())
        {
            var repository = new RunRepository(context, TimeProvider.System, new FixedCurrentUser("other:" + owner), NullLogger<RunRepository>.Instance);
            var run = comparison with { Id = Guid.NewGuid(), SampleId = sample.Id };
            await Assert.ThrowsAsync<AmrException>(() => repository.SaveComparisonAsync(run, CancellationToken.None));
        }
        await using (var context = db.CreateContext())
        {
            var different = await new SampleRepository(context, new FixedCurrentUser(owner), TimeProvider.System).CreateAsync(new CreateSampleRequest { Label = "Different", ResistanceProfile = [1, 1, 1, 1, 1, 1, 1] }, CancellationToken.None);
            var repository = new RunRepository(context, TimeProvider.System, new FixedCurrentUser(owner), NullLogger<RunRepository>.Instance);
            var run = comparison with { Id = Guid.NewGuid(), SampleId = different.Id };
            await Assert.ThrowsAsync<AmrException>(() => repository.SaveComparisonAsync(run, CancellationToken.None));
        }
        await using var read = db.CreateContext();
        var saved = await new SampleRepository(read, new FixedCurrentUser(owner), TimeProvider.System).FindAsync(sample.Id, CancellationToken.None);
        Assert.NotNull(saved);
        Assert.Empty(saved.Runs);
    }
}
