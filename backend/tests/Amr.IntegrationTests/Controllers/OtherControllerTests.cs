using System.Net;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Health;
using Amr.Application.DTOs.Recommendations;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Services;
using Amr.Domain.Enums;
using Amr.IntegrationTests.Infrastructure;

namespace Amr.IntegrationTests.Controllers;

public class ComparisonsControllerTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private const string Url = "/api/v1/comparisons";
    private const string ValidBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"environmentSeed":100001,"policySeed":900001}""";

    private (HttpClient Client, FakeComparisonService Fake) Host(Func<CreateComparisonRequest, CancellationToken, Task<ComparisonDto>>? run = null)
    {
        var fake = new FakeComparisonService { Run = run ?? ((_, _) => SampleDtos.Comparison()) };
        return (factory.WithWebHostBuilder(builder => builder.Use<IComparisonService>(fake)).CreateClient(), fake);
    }

    [Fact]
    public async Task A_valid_request_reaches_the_service_and_returns_both_strategies_with_the_contract()
    {
        var (client, fake) = Host();

        var response = await client.PostJsonAsync(Url, ValidBody);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var request = Assert.Single(fake.RunRequests);
        Assert.Equal((100001L, 900001L), (request.EnvironmentSeed, request.PolicySeed));
        var body = await response.ReadJsonAsync();
        Assert.Equal("ppo", body.GetProperty("ppo").GetProperty("strategy").GetString());
        Assert.Equal("random_susceptible_baseline", body.GetProperty("baseline").GetProperty("strategy").GetString());
        Assert.False(body.GetProperty("isPersisted").GetBoolean());
        Assert.False(body.TryGetProperty("greedy", out _));
    }

    [Fact]
    public async Task The_contract_is_reported_with_its_limits()
    {
        var (client, _) = Host();

        var contract = (await (await client.PostJsonAsync(Url, ValidBody)).ReadJsonAsync()).GetProperty("contract");

        Assert.True(contract.GetProperty("verified").GetBoolean());
        Assert.False(contract.GetProperty("transitionOutcomesGuaranteedIdentical").GetBoolean());
        Assert.True(contract.GetProperty("transitionSeedSchedule").GetProperty("sharedByStepIndex").GetBoolean());
    }

    [Theory]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0]}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0,0]}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,2]}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"environmentSeed":-5}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"policySeed":99999999999}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"horizon":3}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"strategy":"ppo"}""")]
    public async Task Invalid_requests_are_422_and_never_reach_the_service(string body)
    {
        var (client, fake) = Host();

        var response = await client.PostJsonAsync(Url, body);

        await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
        Assert.Empty(fake.RunRequests);
    }

    [Fact]
    public async Task A_contract_violation_is_a_500_with_the_safe_message_and_no_comparison()
    {
        var (client, _) = Host((_, _) => throw new AmrException(ErrorCategory.Internal, ErrorCodes.ComparisonContractViolation, "The comparison could not be verified as like for like."));

        var response = await client.PostJsonAsync(Url, ValidBody);

        var problem = await response.ReadProblemAsync(HttpStatusCode.InternalServerError, ErrorCodes.ComparisonContractViolation);
        Assert.False(problem.TryGetProperty("ppo", out _));
        Assert.DoesNotContain("existing_matched_run_validation", problem.GetRawText(), StringComparison.Ordinal);
    }

    [Fact]
    public async Task An_unavailable_model_is_a_503()
    {
        var (client, _) = Host((_, _) => throw new AmrException(ErrorCategory.DependencyUnavailable, ErrorCodes.ModelUnavailable, "The model is unavailable."));

        var response = await client.PostJsonAsync(Url, ValidBody);

        await response.ReadProblemAsync(HttpStatusCode.ServiceUnavailable, ErrorCodes.ModelUnavailable);
    }

    [Fact]
    public async Task Get_by_id_is_200_when_found_and_a_404_problem_when_absent()
    {
        var fake = new FakeComparisonService { Get = async (id, _) => id == Guid.Empty ? null : await SampleDtos.Comparison() };
        var client = factory.WithWebHostBuilder(builder => builder.Use<IComparisonService>(fake)).CreateClient();

        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync($"{Url}/{Guid.NewGuid()}")).StatusCode);
        await (await client.GetAsync($"{Url}/{Guid.Empty}")).ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.NotFound);
        await (await client.GetAsync($"{Url}/nope")).ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.NotFound);
    }
}

public class RecommendationsControllerTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private const string Url = "/api/v1/recommendations";

    [Fact]
    public async Task A_stored_recommendation_is_returned_with_its_steps_and_interpretation()
    {
        var simulation = await SampleDtos.Simulation();
        var id = Guid.NewGuid();
        var dto = new RecommendationDto(id, StrategyKind.Ppo, simulation.Result!.DisplayLabel, simulation.Provenance, simulation.Result.InitialProfile, false, simulation.Result.TerminationReason, simulation.Result.Steps, "Simulation output.");
        var fake = new FakeRecommendationService { Get = (_, _) => Task.FromResult<RecommendationDto?>(dto) };
        var client = factory.WithWebHostBuilder(builder => builder.Use<IRecommendationService>(fake)).CreateClient();

        var response = await client.GetAsync($"{Url}/{id}");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.ReadJsonAsync();
        Assert.Equal(id, body.GetProperty("simulationId").GetGuid());
        Assert.Equal(simulation.Result.Steps.Count, body.GetProperty("steps").GetArrayLength());
    }

    [Fact]
    public async Task A_run_without_ppo_steps_is_a_recommendation_specific_404()
    {
        var fake = new FakeRecommendationService { Get = (_, _) => Task.FromResult<RecommendationDto?>(null) };
        var client = factory.WithWebHostBuilder(builder => builder.Use<IRecommendationService>(fake)).CreateClient();

        var response = await client.GetAsync($"{Url}/{Guid.NewGuid()}");

        await response.ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.RecommendationNotFound);
    }

    [Fact]
    public async Task A_malformed_id_is_a_generic_404()
    {
        var fake = new FakeRecommendationService();
        var client = factory.WithWebHostBuilder(builder => builder.Use<IRecommendationService>(fake)).CreateClient();

        await (await client.GetAsync($"{Url}/not-a-guid")).ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.NotFound);
    }
}

public class ProfilesControllerTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private const string Url = "/api/v1/profiles/validate";

    private (HttpClient Client, FakeProfileValidationService Fake) Host()
    {
        var fake = new FakeProfileValidationService { Validate = (_, _) => SampleDtos.TerminalProfile() };
        return (factory.WithWebHostBuilder(builder => builder.Use<IProfileValidationService>(fake)).CreateClient(), fake);
    }

    [Fact]
    public async Task A_valid_all_resistant_profile_is_a_200_terminal_result_not_an_error()
    {
        var (client, fake) = Host();

        var response = await client.PostJsonAsync(Url, """{"resistanceProfile":[1,1,1,1,1,1,1]}""");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(new[] { 1, 1, 1, 1, 1, 1, 1 }, Assert.Single(fake.Requests).ResistanceProfile);
        var body = await response.ReadJsonAsync();
        Assert.True(body.GetProperty("isTerminal").GetBoolean());
        Assert.Equal(0, body.GetProperty("feasibleActions").GetArrayLength());
    }

    [Theory]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0]}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0,0]}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,2]}""")]
    [InlineData("""{"resistanceProfile":["a",0,0,0,0,0,0]}""")]
    [InlineData("""{"resistanceProfile":null}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"strategy":"ppo"}""")]
    [InlineData("""{}""")]
    public async Task Malformed_profiles_are_422_and_never_reach_the_service(string body)
    {
        var (client, fake) = Host();

        var response = await client.PostJsonAsync(Url, body);

        var problem = await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
        Assert.True(problem.TryGetProperty("errors", out _));
        Assert.Empty(fake.Requests);
    }
}

public class ModelAndAntibioticsControllerTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private HttpClient Client(FakeModelInfoService fake) =>
        factory.WithWebHostBuilder(builder => builder.Use<IModelInfoService>(fake)).CreateClient();

    [Fact]
    public async Task Model_info_is_returned_in_public_shape_without_internal_details()
    {
        var client = Client(new FakeModelInfoService { Model = _ => SampleDtos.Model() });

        var response = await client.GetAsync("/api/v1/model");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var text = await response.Content.ReadAsStringAsync();
        Assert.Contains("\"checkpointSha256\":\"d10c26185c9903d96d0f2003643b76be6df4f03c39e0d2e5f7945e763b7d9093\"", text, StringComparison.Ordinal);
        Assert.DoesNotContain("artifacts/", text, StringComparison.Ordinal);
        Assert.DoesNotContain("\\\\", text, StringComparison.Ordinal);
    }

    [Fact]
    public async Task The_antibiotic_catalogue_is_returned_in_python_order()
    {
        var client = Client(new FakeModelInfoService { Antibiotics = _ => SampleDtos.Antibiotics() });

        var body = await (await client.GetAsync("/api/v1/antibiotics")).ReadJsonAsync();

        var ids = body.GetProperty("antibiotics").EnumerateArray().Select(item => item.GetProperty("actionId").GetInt32());
        Assert.Equal(Enumerable.Range(0, 7), ids);
    }

    [Fact]
    public async Task An_unavailable_model_is_a_503_problem()
    {
        var client = Client(new FakeModelInfoService { Model = _ => throw new AmrException(ErrorCategory.DependencyUnavailable, ErrorCodes.ModelUnavailable, "The model is unavailable.") });

        await (await client.GetAsync("/api/v1/model")).ReadProblemAsync(HttpStatusCode.ServiceUnavailable, ErrorCodes.ModelUnavailable);
    }
}

public class HealthControllerTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private static HealthDto Report(bool ready) => new(
        ready ? HealthState.Healthy : HealthState.Unhealthy,
        ready,
        [
            new ComponentHealthDto(HealthComponents.Api, HealthState.Healthy, null),
            new ComponentHealthDto(HealthComponents.Model, ready ? HealthState.Healthy : HealthState.Unhealthy, ready ? null : ErrorCodes.ModelUnavailable),
        ]);

    private HttpClient Client(FakeHealthService fake) =>
        factory.WithWebHostBuilder(builder => builder.Use<IHealthService>(fake)).CreateClient();

    [Fact]
    public async Task A_ready_report_is_200()
    {
        var response = await Client(new FakeHealthService { Readiness = _ => Task.FromResult(Report(true)) }).GetAsync("/api/v1/health");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var body = await response.ReadJsonAsync();
        Assert.Equal("healthy", body.GetProperty("status").GetString());
        Assert.True(body.GetProperty("ready").GetBoolean());
    }

    [Fact]
    public async Task A_not_ready_report_is_503_with_the_same_report_body()
    {
        var response = await Client(new FakeHealthService { Readiness = _ => Task.FromResult(Report(false)) }).GetAsync("/api/v1/health");

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        var body = await response.ReadJsonAsync();
        Assert.False(body.GetProperty("ready").GetBoolean());
        Assert.Equal("model_unavailable", body.GetProperty("components").EnumerateArray().Single(item => item.GetProperty("name").GetString() == "model").GetProperty("detail").GetString());
    }

    [Fact]
    public async Task Liveness_is_200_even_when_readiness_would_fail_and_never_calls_readiness()
    {
        var calls = 0;
        var fake = new FakeHealthService { Readiness = _ => { calls++; return Task.FromResult(Report(false)); } };

        var response = await Client(fake).GetAsync("/api/v1/health/live");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(0, calls);
    }
}
