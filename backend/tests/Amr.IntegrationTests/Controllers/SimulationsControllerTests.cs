using System.Net;
using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Amr.Domain.Enums;
using Amr.IntegrationTests.Infrastructure;

namespace Amr.IntegrationTests.Controllers;

public class SimulationsControllerTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private const string Url = "/api/v1/simulations";
    private const string ValidBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"ppo","environmentSeed":100001}""";

    private (HttpClient Client, FakeSimulationService Fake) Host(Func<CreateSimulationRequest, CancellationToken, Task<SimulationDto>>? run = null)
    {
        var fake = new FakeSimulationService { Run = run ?? ((_, _) => SampleDtos.Simulation()) };
        var client = factory.WithWebHostBuilder(builder => builder.Use<Amr.Application.Interfaces.Services.ISimulationService>(fake)).CreateClient();
        return (client, fake);
    }

    [Fact]
    public async Task A_valid_request_reaches_the_service_with_typed_values_and_returns_200()
    {
        var (client, fake) = Host();

        var response = await client.PostJsonAsync(Url, """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"random_susceptible_baseline","environmentSeed":7,"policySeed":9}""");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var request = Assert.Single(fake.RunRequests);
        Assert.Equal(new[] { 0, 1, 0, 0, 0, 0, 0 }, request.ResistanceProfile);
        Assert.Equal((StrategyKind.RandomSusceptibleBaseline, 7L, 9L), (request.Strategy, request.EnvironmentSeed, request.PolicySeed));
    }

    [Fact]
    public async Task The_response_shape_is_camel_case_with_snake_case_enums_and_explicit_non_persistence()
    {
        var (client, _) = Host((_, _) => SampleDtos.Simulation(StrategyKind.RandomSusceptibleBaseline));

        var body = await (await client.PostJsonAsync(Url, ValidBody)).ReadJsonAsync();

        Assert.Equal("completed", body.GetProperty("status").GetString());
        Assert.False(body.GetProperty("isPersisted").GetBoolean());
        Assert.Equal("random_susceptible_baseline", body.GetProperty("result").GetProperty("strategy").GetString());
        Assert.Equal("Random Susceptible Baseline", body.GetProperty("result").GetProperty("displayLabel").GetString());
        Assert.Equal("normalized_resistance_burden", body.GetProperty("provenance").GetProperty("rewardSpecification").GetProperty("objective").GetString());
        Assert.True(body.GetProperty("provenance").TryGetProperty("checkpointSha256", out _));
        Assert.False(body.GetProperty("result").TryGetProperty("implementation", out _));
    }

    [Fact]
    public async Task Unsupported_transition_statuses_reach_the_client_unchanged()
    {
        var (client, _) = Host();

        var body = await (await client.PostJsonAsync(Url, ValidBody)).ReadJsonAsync();

        var statuses = body.GetProperty("result").GetProperty("steps").EnumerateArray().Select(step => step.GetProperty("transitionStatus").GetString()).ToList();
        Assert.Contains("unsupported_no_candidate", statuses);
        var step = body.GetProperty("result").GetProperty("steps").EnumerateArray().First(item => item.GetProperty("transitionStatus").GetString() == "unsupported_no_candidate");
        Assert.False(step.GetProperty("hasCandidateTransition").GetBoolean());
        Assert.Equal(JsonValueKindNull, step.GetProperty("selectedOutcome").ValueKind);
    }

    private const System.Text.Json.JsonValueKind JsonValueKindNull = System.Text.Json.JsonValueKind.Null;

    [Fact]
    public async Task A_valid_terminal_run_is_a_200_with_no_steps()
    {
        var (client, _) = Host((_, _) => SampleDtos.TerminalSimulation());

        var response = await client.PostJsonAsync(Url, """{"resistanceProfile":[1,1,1,1,1,1,1],"strategy":"ppo","environmentSeed":1}""");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var result = (await response.ReadJsonAsync()).GetProperty("result");
        Assert.Equal(0, result.GetProperty("steps").GetArrayLength());
        Assert.Equal("no_effective_antibiotic", result.GetProperty("terminationReason").GetString());
    }

    [Theory]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0],"strategy":"ppo"}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,2],"strategy":"ppo"}""")]
    [InlineData("""{"resistanceProfile":["0",0,0,0,0,0,0],"strategy":"ppo"}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"strategy":"greedy"}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"strategy":"value_iteration"}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0]}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"strategy":"ppo","environmentSeed":-1}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"strategy":"ppo","policySeed":4294967296}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"strategy":"ppo","horizon":3}""")]
    [InlineData("""{"resistanceProfile":[0,0,0,0,0,0,0],"strategy":"ppo","scenarioId":"SENSITIVITY_Q_050"}""")]
    public async Task Invalid_requests_are_422_and_never_reach_the_service(string body)
    {
        var (client, fake) = Host();

        var response = await client.PostJsonAsync(Url, body);

        await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
        Assert.Empty(fake.RunRequests);
    }

    [Theory]
    [InlineData(ErrorCategory.DependencyUnavailable, ErrorCodes.ModelUnavailable, HttpStatusCode.ServiceUnavailable)]
    [InlineData(ErrorCategory.DependencyUnavailable, ErrorCodes.PythonServiceTimeout, HttpStatusCode.ServiceUnavailable)]
    [InlineData(ErrorCategory.UpstreamFailure, ErrorCodes.PythonServiceInvalidResponse, HttpStatusCode.BadGateway)]
    [InlineData(ErrorCategory.InvalidRequest, ErrorCodes.ValidationFailed, HttpStatusCode.UnprocessableEntity)]
    [InlineData(ErrorCategory.Internal, ErrorCodes.InternalError, HttpStatusCode.InternalServerError)]
    public async Task Application_errors_become_problems_with_their_stable_codes(ErrorCategory category, string code, HttpStatusCode status)
    {
        var (client, _) = Host((_, _) => throw new AmrException(category, code, "Safe message."));

        var response = await client.PostJsonAsync(Url, ValidBody);

        var problem = await response.ReadProblemAsync(status, code);
        Assert.Equal("Safe message.", problem.GetProperty("detail").GetString());
    }

    [Fact]
    public async Task Client_cancellation_reaches_the_application_service()
    {
        var observed = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var (client, _) = Host(async (_, token) =>
        {
            token.Register(() => observed.TrySetResult(true));
            await Task.Delay(Timeout.Infinite, token);
            return await SampleDtos.Simulation();
        });
        using var cancellation = new CancellationTokenSource();

        var pending = client.PostAsync(Url, new StringContent(ValidBody, System.Text.Encoding.UTF8, "application/json"), cancellation.Token);
        await Task.Delay(300);
        await cancellation.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => pending);
        Assert.True(await Task.WhenAny(observed.Task, Task.Delay(TimeSpan.FromSeconds(5))) == observed.Task, "The service never saw the cancellation.");
    }

    [Fact]
    public async Task Get_by_id_returns_the_simulation_when_the_service_has_it_and_a_404_problem_when_it_does_not()
    {
        var fake = new FakeSimulationService { Get = async (id, _) => id == Guid.Empty ? null : await SampleDtos.Simulation() };
        var client = factory.WithWebHostBuilder(builder => builder.Use<Amr.Application.Interfaces.Services.ISimulationService>(fake)).CreateClient();
        var existing = Guid.NewGuid();

        var found = await client.GetAsync($"{Url}/{existing}");
        var missing = await client.GetAsync($"{Url}/{Guid.Empty}");

        Assert.Equal(HttpStatusCode.OK, found.StatusCode);
        await missing.ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.NotFound);
        Assert.Equal(new[] { existing, Guid.Empty }, fake.GetIds);
    }

    [Theory]
    [InlineData("not-a-guid")]
    [InlineData("123")]
    public async Task A_malformed_id_is_a_routing_404_and_never_reaches_the_service(string id)
    {
        var fake = new FakeSimulationService();
        var client = factory.WithWebHostBuilder(builder => builder.Use<Amr.Application.Interfaces.Services.ISimulationService>(fake)).CreateClient();

        var response = await client.GetAsync($"{Url}/{id}");

        await response.ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.NotFound);
        Assert.Empty(fake.GetIds);
    }

    [Fact]
    public async Task Recent_is_routed_to_history_not_to_get_by_id_and_uses_the_default_paging()
    {
        var history = new FakeRunHistoryService { Recent = (query, _) => Task.FromResult(new PagedResultDto<RunSummaryDto>([], query.Page, query.PageSize, 0)) };
        var simulations = new FakeSimulationService();
        var client = factory.WithWebHostBuilder(builder => builder
            .Use<Amr.Application.Interfaces.Services.IRunHistoryService>(history)
            .Use<Amr.Application.Interfaces.Services.ISimulationService>(simulations)).CreateClient();

        var body = await (await client.GetAsync($"{Url}/recent")).ReadJsonAsync();

        Assert.Equal((1, PaginationLimits.DefaultPageSize), (history.Queries.Single().Page, history.Queries.Single().PageSize));
        Assert.Empty(simulations.GetIds);
        Assert.Equal((1, 20, 0), (body.GetProperty("page").GetInt32(), body.GetProperty("pageSize").GetInt32(), body.GetProperty("totalCount").GetInt32()));
    }

    [Theory]
    [InlineData("page=0")]
    [InlineData("pageSize=51")]
    [InlineData("pageSize=0")]
    [InlineData("page=abc")]
    public async Task Out_of_range_paging_is_422_and_never_reaches_the_service(string query)
    {
        var history = new FakeRunHistoryService();
        var client = factory.WithWebHostBuilder(builder => builder.Use<Amr.Application.Interfaces.Services.IRunHistoryService>(history)).CreateClient();

        var response = await client.GetAsync($"{Url}/recent?{query}");

        await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
        Assert.Empty(history.Queries);
    }
}
