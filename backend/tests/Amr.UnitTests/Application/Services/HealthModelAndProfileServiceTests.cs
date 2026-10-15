using System.Net;
using Amr.Application.DTOs.Health;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Amr.Application.Services;

namespace Amr.UnitTests.Application.Services;

public class HealthModelAndProfileServiceTests
{
    private sealed class FakeProbe(params ComponentHealthDto[] components) : IDependencyHealthProbe
    {
        public int Calls { get; private set; }

        public Task<IReadOnlyList<ComponentHealthDto>> CheckAsync(CancellationToken cancellationToken)
        {
            Calls++;
            return Task.FromResult<IReadOnlyList<ComponentHealthDto>>(components);
        }
    }

    private static ComponentHealthDto Healthy(string name) => new(name, HealthState.Healthy, null);

    private static ComponentHealthDto Unhealthy(string name, string detail) => new(name, HealthState.Unhealthy, detail);

    [Fact]
    public async Task All_dependencies_healthy_is_ready_and_lists_the_api_first()
    {
        var service = new HealthService([new FakeProbe(Healthy(HealthComponents.PythonService), Healthy(HealthComponents.Model))]);

        var report = await service.GetHealthAsync(CancellationToken.None);

        Assert.Equal((HealthState.Healthy, true), (report.Status, report.Ready));
        Assert.Equal(new[] { HealthComponents.Api, HealthComponents.PythonService, HealthComponents.Model }, report.Components.Select(component => component.Name));
    }

    [Fact]
    public async Task A_running_api_with_an_unverified_model_is_not_ready()
    {
        var service = new HealthService([new FakeProbe(Healthy(HealthComponents.PythonService), Unhealthy(HealthComponents.Model, ErrorCodes.ModelUnavailable))]);

        var report = await service.GetHealthAsync(CancellationToken.None);

        Assert.Equal((HealthState.Unhealthy, false), (report.Status, report.Ready));
        Assert.Equal(HealthState.Healthy, report.Components.Single(component => component.Name == HealthComponents.Api).Status);
        Assert.Equal(ErrorCodes.ModelUnavailable, report.Components.Single(component => component.Name == HealthComponents.Model).Detail);
    }

    [Fact]
    public async Task An_unreachable_python_service_is_not_ready_and_reports_only_stable_codes()
    {
        var service = new HealthService([new FakeProbe(Unhealthy(HealthComponents.PythonService, ErrorCodes.PythonServiceUnavailable), Unhealthy(HealthComponents.Model, ErrorCodes.ModelUnavailable))]);

        var report = await service.GetHealthAsync(CancellationToken.None);

        Assert.False(report.Ready);
        Assert.All(report.Components.Where(component => component.Status == HealthState.Unhealthy), component => Assert.Matches("^[a-z_]+$", component.Detail!));
    }

    [Fact]
    public async Task Every_registered_probe_is_consulted_and_the_worst_state_wins()
    {
        var first = new FakeProbe(Healthy(HealthComponents.PythonService));
        var second = new FakeProbe(new ComponentHealthDto(HealthComponents.Database, HealthState.Degraded, "slow"));
        var service = new HealthService([first, second]);

        var report = await service.GetHealthAsync(CancellationToken.None);

        Assert.Equal((1, 1), (first.Calls, second.Calls));
        Assert.Equal((HealthState.Degraded, false), (report.Status, report.Ready));
    }

    [Fact]
    public void Liveness_touches_no_dependency_and_reports_only_the_api()
    {
        var probe = new FakeProbe(Unhealthy(HealthComponents.PythonService, "x"));

        var report = new HealthService([probe]).GetLiveness();

        Assert.Equal(0, probe.Calls);
        Assert.Equal((HealthState.Healthy, true), (report.Status, report.Ready));
        Assert.Equal(HealthComponents.Api, Assert.Single(report.Components).Name);
    }

    [Fact]
    public async Task Cancellation_is_passed_to_probes()
    {
        var service = new HealthService([new CancellingProbe()]);
        using var cancellation = new CancellationTokenSource();
        await cancellation.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => service.GetHealthAsync(cancellation.Token));
    }

    private sealed class CancellingProbe : IDependencyHealthProbe
    {
        public Task<IReadOnlyList<ComponentHealthDto>> CheckAsync(CancellationToken cancellationToken) =>
            Task.FromCanceled<IReadOnlyList<ComponentHealthDto>>(cancellationToken);
    }

    [Fact]
    public async Task Model_info_is_mapped_without_internal_paths_or_devices_and_keeps_verified_hashes()
    {
        var handler = StubHandler.Returning(() => PythonFixtures.Fixture("model_200"));

        var model = await new ModelInfoService(ClientFactory.Create(handler)).GetModelAsync(CancellationToken.None);

        Assert.Equal("ppo_seed_12000", model.ModelId);
        Assert.Equal("d10c26185c9903d96d0f2003643b76be6df4f03c39e0d2e5f7945e763b7d9093", model.CheckpointSha256);
        Assert.Equal("7a5e3e1fe730676a0793674e4ff4aaf3c6ce1177ad5588eed4bb2e5d627edb44", model.InteractionDataSha256);
        Assert.Equal(("REF_UNIFORM_SUPPORTED", 8, "susceptible_actions_only", true), (model.ScenarioId, model.Horizon, model.ActionMaskRule, model.DeterministicInference));
        Assert.Equal(("Discrete", 7), (model.ActionSpace.Type, model.ActionSpace.Count));
        Assert.Equal(new[] { 15 }, model.Observation.Shape);
        var serialized = System.Text.Json.JsonSerializer.Serialize(model);
        Assert.DoesNotContain("artifacts/", serialized, StringComparison.Ordinal);
        Assert.DoesNotContain("cpu", serialized, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("unsupported_no_candidate", model.TransitionStatusDefinitions.Keys);
    }

    [Fact]
    public async Task The_antibiotic_catalogue_keeps_python_order_and_drug_classes()
    {
        var handler = StubHandler.Returning(() => PythonFixtures.Fixture("antibiotics_200"));

        var catalogue = await new ModelInfoService(ClientFactory.Create(handler)).GetAntibioticsAsync(CancellationToken.None);

        Assert.Equal(Enumerable.Range(0, 7), catalogue.Antibiotics.Select(item => item.ActionId));
        Assert.Equal("CIPROFLOXACIN", catalogue.Antibiotics[0].Name);
        Assert.Equal("Fluoroquinolone", catalogue.Antibiotics[0].DrugClass);
        Assert.Equal(1, catalogue.ResistanceEncoding["resistant"]);
    }

    [Fact]
    public async Task The_model_being_unavailable_surfaces_as_a_503_class_error()
    {
        var handler = StubHandler.Returning(() => PythonFixtures.Fixture("model_503_checkpoint_integrity_failure", HttpStatusCode.ServiceUnavailable));

        var error = await Assert.ThrowsAsync<AmrException>(() => new ModelInfoService(ClientFactory.Create(handler)).GetModelAsync(CancellationToken.None));

        Assert.Equal((ErrorCategory.DependencyUnavailable, ErrorCodes.ModelUnavailable), (error.Category, error.Code));
    }

    [Fact]
    public async Task An_open_profile_lists_feasible_actions_with_their_support_flags()
    {
        var handler = StubHandler.Returning(() => PythonFixtures.Fixture("validate_200_open"));
        var service = new ProfileValidationService(ClientFactory.Create(handler));

        var result = await service.ValidateAsync(new() { ResistanceProfile = [1, 0, 0, 1, 0, 0, 0] }, CancellationToken.None);

        Assert.Equal("""{"resistance_profile":[1,0,0,1,0,0,0]}""", handler.Requests.Single().Body);
        Assert.False(result.IsTerminal);
        Assert.Equal(new[] { 1, 2, 4, 5, 6 }, result.FeasibleActions.Select(action => action.ActionId));
        Assert.Contains(result.FeasibleActions, action => action is { Antibiotic: "GENTAMICIN", HasCandidateTransition: false });
    }

    [Fact]
    public async Task A_valid_all_resistant_profile_is_terminal_with_no_selected_or_feasible_action()
    {
        var handler = StubHandler.Returning(() => PythonFixtures.Fixture("validate_200_terminal"));
        var service = new ProfileValidationService(ClientFactory.Create(handler));

        var result = await service.ValidateAsync(new() { ResistanceProfile = [1, 1, 1, 1, 1, 1, 1] }, CancellationToken.None);

        Assert.True(result.IsTerminal);
        Assert.Equal("no_effective_antibiotic", result.TerminalReason);
        Assert.Empty(result.FeasibleActions);
        Assert.Equal(0, result.SusceptibleOptionCount);
    }

    [Fact]
    public async Task A_python_validation_rejection_is_a_422_class_error_without_python_details()
    {
        var handler = StubHandler.Returning(() => PythonFixtures.Fixture("validate_422_invalid_context", HttpStatusCode.UnprocessableEntity));
        var service = new ProfileValidationService(ClientFactory.Create(handler));

        var error = await Assert.ThrowsAsync<AmrException>(() => service.ValidateAsync(new() { ResistanceProfile = [0, 2, 0, 0, 0, 0, 0] }, CancellationToken.None));

        Assert.Equal((ErrorCategory.InvalidRequest, ErrorCodes.ValidationFailed), (error.Category, error.Code));
        Assert.DoesNotContain("resistance_profile values", error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task A_validation_body_that_says_the_profile_is_not_valid_is_an_invalid_response()
    {
        var body = PythonFixtures.Mutate("validate_200_open", node => node["valid"] = false);
        var handler = StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.OK, body));

        var error = await Assert.ThrowsAsync<AmrException>(() => new ProfileValidationService(ClientFactory.Create(handler)).ValidateAsync(new() { ResistanceProfile = [1, 0, 0, 1, 0, 0, 0] }, CancellationToken.None));

        Assert.Equal(ErrorCodes.PythonServiceInvalidResponse, error.Code);
    }

    [Fact]
    public async Task Stored_recommendations_and_history_are_explicitly_not_implemented_without_persistence()
    {
        var recommendation = await Assert.ThrowsAsync<AmrException>(() => new RecommendationService().GetBySimulationAsync(Guid.NewGuid(), CancellationToken.None));
        var history = await Assert.ThrowsAsync<AmrException>(() => new RunHistoryService().GetRecentAsync(new(), CancellationToken.None));

        Assert.All(new[] { recommendation, history }, error => Assert.Equal((ErrorCategory.NotImplemented, ErrorCodes.PersistenceNotAvailable), (error.Category, error.Code)));
    }
}
