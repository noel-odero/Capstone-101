using Amr.Application.DTOs.Health;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Amr.Application.PythonContracts;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.Extensions.DependencyInjection;

namespace Amr.IntegrationTests;

/// <summary>Exercises the real Python service through the real typed client. Skipped unless AMR_PYTHON_URL is set.</summary>
public sealed class LivePythonServiceTests : IDisposable
{
    private const string FrozenCheckpointSha256 = "d10c26185c9903d96d0f2003643b76be6df4f03c39e0d2e5f7945e763b7d9093";
    private readonly AmrApiFactory _factory;
    private readonly IPythonServiceClient _client;

    public LivePythonServiceTests()
    {
        var url = LiveFactAttribute.Url;
        _factory = new AmrApiFactory();
        if (url is null)
        {
            _client = null!;
            return;
        }

        var configured = _factory.WithWebHostBuilder(builder => builder.UseSetting("PythonService:BaseUrl", url));
        _client = configured.Services.GetRequiredService<IPythonServiceClient>();
        Probe = configured.Services.GetRequiredService<IDependencyHealthProbe>();
    }

    private IDependencyHealthProbe Probe { get; } = null!;

    public void Dispose() => _factory.Dispose();

    [LiveFact]
    public async Task Health_and_the_probe_report_a_ready_verified_model()
    {
        var health = await _client.GetHealthAsync(CancellationToken.None);
        var components = await Probe.CheckAsync(CancellationToken.None);

        Assert.True(health.ModelReady);
        Assert.Equal(FrozenCheckpointSha256, health.CheckpointSha256);
        Assert.All(components, component => Assert.Equal(HealthState.Healthy, component.Status));
    }

    [LiveFact]
    public async Task Model_and_antibiotic_catalogue_deserialize_from_the_real_service()
    {
        var model = await _client.GetModelAsync(CancellationToken.None);
        var antibiotics = await _client.GetAntibioticsAsync(CancellationToken.None);

        Assert.Equal(FrozenCheckpointSha256, model.CheckpointSha256);
        Assert.Equal(model.AntibioticOrder, antibiotics.Antibiotics.Select(item => item.Name));
    }

    [LiveFact]
    public async Task A_python_rejection_surfaces_as_a_public_validation_error()
    {
        var error = await Assert.ThrowsAsync<AmrException>(() => _client.ValidateProfileAsync([0, 2, 0, 0, 0, 0, 0], CancellationToken.None));

        Assert.Equal((ErrorCategory.InvalidRequest, ErrorCodes.ValidationFailed), (error.Category, error.Code));
    }

    [LiveFact]
    public async Task A_terminal_profile_is_a_normal_result()
    {
        var validation = await _client.ValidateProfileAsync([1, 1, 1, 1, 1, 1, 1], CancellationToken.None);
        var run = await _client.SimulateAsync(new PythonSimulateRequest([1, 1, 1, 1, 1, 1, 1], PythonStrategyIds.Ppo, 1, null), CancellationToken.None);

        Assert.True(validation.IsTerminal);
        Assert.Empty(run.Result.Steps);
    }

    [LiveFact]
    public async Task Ppo_and_baseline_simulations_and_a_comparison_round_trip_with_unsupported_transitions_preserved()
    {
        var profile = new[] { 0, 1, 0, 0, 0, 0, 0 };

        var ppo = await _client.SimulateAsync(new PythonSimulateRequest(profile, PythonStrategyIds.Ppo, 100001, null), CancellationToken.None);
        var baseline = await _client.SimulateAsync(new PythonSimulateRequest(profile, PythonStrategyIds.Greedy, 100001, 900001), CancellationToken.None);
        var comparison = await _client.CompareAsync(new PythonCompareRequest(profile, 100001, 900001), CancellationToken.None);

        Assert.Equal(FrozenCheckpointSha256, ppo.Provenance.CheckpointSha256);
        Assert.Equal(8, ppo.Result.Steps.Count);
        Assert.Contains(ppo.Result.Steps, step => step.TransitionStatus == "unsupported_no_candidate");
        Assert.Equal("Random Susceptible Baseline", baseline.Result.DisplayLabel);
        Assert.True(comparison.ComparisonContract.Verified);
        Assert.False(comparison.ComparisonContract.TransitionOutcomesGuaranteedIdentical);
        Assert.Equal(ppo.Result.Steps.Select(step => step.ActionId), comparison.Ppo.Steps.Select(step => step.ActionId));
    }
}
