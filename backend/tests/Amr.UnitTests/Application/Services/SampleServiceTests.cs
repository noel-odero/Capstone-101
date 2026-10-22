using Amr.Application.DTOs.Samples;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Persistence;
using Amr.Application.Services;

namespace Amr.UnitTests.Application.Services;

public class SampleServiceTests
{
    private sealed class Samples(SampleDto? sample) : ISampleRepository
    {
        public int Reads { get; private set; }
        public Task<SampleDto?> FindAsync(Guid id, CancellationToken cancellationToken)
        {
            Reads++;
            return Task.FromResult(sample?.Id == id ? sample : null);
        }
        public Task<SampleDto> CreateAsync(CreateSampleRequest request, CancellationToken cancellationToken) => throw new NotSupportedException();
        public Task<IReadOnlyList<SampleDto>> ListAsync(CancellationToken cancellationToken) => throw new NotSupportedException();
    }

    private static SampleDto Sample() => new(Guid.NewGuid(), "UTI-024", DateTimeOffset.UtcNow, [0, 1, 0, 0, 0, 0, 0], []);

    [Fact]
    public async Task An_unlinked_run_does_not_read_samples()
    {
        var samples = new Samples(null);
        await new SampleService(samples).ValidateRunAsync(null, [0, 0, 0, 0, 0, 0, 0], CancellationToken.None);
        Assert.Equal(0, samples.Reads);
    }

    [Fact]
    public async Task A_saved_profile_can_be_used_for_a_run()
    {
        var sample = Sample();
        var samples = new Samples(sample);
        await new SampleService(samples).ValidateRunAsync(sample.Id, sample.ResistanceProfile, CancellationToken.None);
        Assert.Equal(1, samples.Reads);
    }

    [Fact]
    public async Task A_missing_or_unowned_sample_is_not_found()
    {
        var exception = await Assert.ThrowsAsync<AmrException>(() => new SampleService(new Samples(null)).ValidateRunAsync(Guid.NewGuid(), [0, 0, 0, 0, 0, 0, 0], CancellationToken.None));
        Assert.Equal(ErrorCategory.NotFound, exception.Category);
        Assert.Equal("sample_not_found", exception.Code);
    }

    [Fact]
    public async Task A_changed_profile_is_rejected_before_execution()
    {
        var sample = Sample();
        var exception = await Assert.ThrowsAsync<AmrException>(() => new SampleService(new Samples(sample)).ValidateRunAsync(sample.Id, [1, 0, 0, 0, 0, 0, 0], CancellationToken.None));
        Assert.Equal(ErrorCategory.InvalidRequest, exception.Category);
        Assert.Equal("sample_profile_mismatch", exception.Code);
    }
}
