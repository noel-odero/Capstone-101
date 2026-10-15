using Amr.Application.DTOs.Health;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Amr.Application.PythonContracts;
using Amr.Infrastructure.Python;
using Microsoft.Extensions.Logging.Abstractions;

namespace Amr.UnitTests.Infrastructure.Python;

public class PythonServiceHealthCheckerTests
{
    private sealed class HealthOnlyClient(Func<CancellationToken, Task<PythonHealth>> health) : IPythonServiceClient
    {
        public Task<PythonHealth> GetHealthAsync(CancellationToken cancellationToken) => health(cancellationToken);

        public Task<PythonModelInfo> GetModelAsync(CancellationToken cancellationToken) => throw new NotSupportedException();

        public Task<PythonAntibiotics> GetAntibioticsAsync(CancellationToken cancellationToken) => throw new NotSupportedException();

        public Task<PythonProfileValidation> ValidateProfileAsync(IReadOnlyList<int> resistanceProfile, CancellationToken cancellationToken) => throw new NotSupportedException();

        public Task<PythonSimulation> SimulateAsync(PythonSimulateRequest request, CancellationToken cancellationToken) => throw new NotSupportedException();

        public Task<PythonComparison> CompareAsync(PythonCompareRequest request, CancellationToken cancellationToken) => throw new NotSupportedException();
    }

    private static PythonServiceHealthChecker Checker(Func<CancellationToken, Task<PythonHealth>> health) =>
        new(new HealthOnlyClient(health), NullLogger<PythonServiceHealthChecker>.Instance);

    private static PythonHealth Health(bool modelReady, string status = "ok", string? errorCode = null) =>
        new(status, modelReady, "0.1.0", modelReady ? "ppo_seed_12000" : null, modelReady ? "abc" : null, errorCode, "message");

    private static ComponentHealthDto Component(IReadOnlyList<ComponentHealthDto> components, string name) =>
        components.Single(component => component.Name == name);

    [Fact]
    public async Task A_reachable_service_with_a_verified_model_makes_both_components_healthy()
    {
        var components = await Checker(_ => Task.FromResult(Health(modelReady: true))).CheckAsync(CancellationToken.None);

        Assert.Equal(new ComponentHealthDto(HealthComponents.PythonService, HealthState.Healthy, null), Component(components, HealthComponents.PythonService));
        Assert.Equal(new ComponentHealthDto(HealthComponents.Model, HealthState.Healthy, null), Component(components, HealthComponents.Model));
    }

    [Fact]
    public async Task A_running_service_is_not_ready_when_its_model_failed_verification()
    {
        var components = await Checker(_ => Task.FromResult(Health(modelReady: false, "unavailable", "checkpoint_integrity_failure")))
            .CheckAsync(CancellationToken.None);

        Assert.Equal(HealthState.Healthy, Component(components, HealthComponents.PythonService).Status);
        var model = Component(components, HealthComponents.Model);
        Assert.Equal((HealthState.Unhealthy, ErrorCodes.ModelUnavailable), (model.Status, model.Detail));
        Assert.DoesNotContain(components, component => component.Detail == "checkpoint_integrity_failure");
    }

    [Fact]
    public async Task An_inconsistent_health_body_is_not_treated_as_ready()
    {
        var components = await Checker(_ => Task.FromResult(Health(modelReady: true, status: "unavailable"))).CheckAsync(CancellationToken.None);

        Assert.Equal(HealthState.Unhealthy, Component(components, HealthComponents.Model).Status);
    }

    [Theory]
    [InlineData(ErrorCodes.PythonServiceUnavailable)]
    [InlineData(ErrorCodes.PythonServiceTimeout)]
    [InlineData(ErrorCodes.PythonServiceInvalidResponse)]
    public async Task An_unreachable_slow_or_incoherent_service_makes_both_components_unhealthy_with_a_stable_code(string code)
    {
        var category = code == ErrorCodes.PythonServiceInvalidResponse ? ErrorCategory.UpstreamFailure : ErrorCategory.DependencyUnavailable;
        var components = await Checker(_ => throw new AmrException(category, code, "safe")).CheckAsync(CancellationToken.None);

        var service = Component(components, HealthComponents.PythonService);
        Assert.Equal((HealthState.Unhealthy, code), (service.Status, service.Detail));
        var model = Component(components, HealthComponents.Model);
        Assert.Equal((HealthState.Unhealthy, ErrorCodes.ModelUnavailable), (model.Status, model.Detail));
    }

    [Fact]
    public async Task Cancellation_is_not_swallowed_as_an_unhealthy_dependency()
    {
        using var cancellation = new CancellationTokenSource();
        var checker = Checker(token => Task.FromCanceled<PythonHealth>(token));
        await cancellation.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => checker.CheckAsync(cancellation.Token));
    }

    [Fact]
    public async Task Unexpected_non_application_exceptions_are_not_hidden()
    {
        var checker = Checker(_ => throw new InvalidOperationException("bug"));

        await Assert.ThrowsAsync<InvalidOperationException>(() => checker.CheckAsync(CancellationToken.None));
    }
}
