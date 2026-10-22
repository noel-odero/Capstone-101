using Amr.Application.DTOs.Samples;
using Amr.Application.Errors;
using Amr.Infrastructure.Persistence;
using Amr.IntegrationTests.Infrastructure;
using Amr.TestSupport;
using Microsoft.Extensions.Logging.Abstractions;

namespace Amr.IntegrationTests.Persistence;

public class SampleRepositoryTests(PostgresDatabaseFixture db) : IClassFixture<PostgresDatabaseFixture>
{
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
