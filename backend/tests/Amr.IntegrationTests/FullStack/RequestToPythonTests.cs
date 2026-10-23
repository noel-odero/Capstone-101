using System.Net;
using System.Text.Json.Nodes;
using Amr.Application.Errors;
using Amr.IntegrationTests.Infrastructure;

namespace Amr.IntegrationTests.FullStack;

/// <summary>Request-to-Python path through the real controllers, services and Python client, with only the network stubbed. None of these reach the database.</summary>
public class RequestToPythonTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private const string PpoBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"ppo","environmentSeed":100001}""";
    private const string CompareBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"environmentSeed":100001,"policySeed":900001}""";

    private static JsonNode SentBody(StubHandler python) => JsonNode.Parse(python.Requests.Single().Body!)!;

    [Fact]
    public async Task Model_comes_from_python_without_internal_paths_or_devices()
    {
        var (client, python) = StubbedPythonHost.Create(factory);

        var response = await client.GetAsync("/api/v1/model");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal("/internal/model", python.Requests.Single().Uri.AbsolutePath);
        var text = await response.Content.ReadAsStringAsync();
        Assert.Contains("ppo_public_v2_seed_19000", text, StringComparison.Ordinal);
        Assert.DoesNotContain("artifacts/", text, StringComparison.Ordinal);
        Assert.DoesNotContain("python.test", text, StringComparison.Ordinal);
    }

    [Fact]
    public async Task Antibiotics_come_from_python_in_action_order()
    {
        var (client, _) = StubbedPythonHost.Create(factory);

        var body = await (await client.GetAsync("/api/v1/antibiotics")).ReadJsonAsync();

        Assert.Equal(7, body.GetProperty("antibiotics").GetArrayLength());
        Assert.Equal("CIPROFLOXACIN", body.GetProperty("antibiotics")[0].GetProperty("name").GetString());
    }

    [Fact]
    public async Task A_terminal_profile_is_a_200_result_from_python_not_an_error()
    {
        var (client, python) = StubbedPythonHost.Create(factory);

        var response = await client.PostJsonAsync("/api/v1/profiles/validate", """{"resistanceProfile":[1,1,1,1,1,1,1]}""");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal("/internal/profiles/validate", python.Requests.Single().Uri.AbsolutePath);
        Assert.Equal(new[] { 1, 1, 1, 1, 1, 1, 1 }, SentBody(python)["resistance_profile"]!.AsArray().Select(node => node!.GetValue<int>()));
        Assert.True((await response.ReadJsonAsync()).GetProperty("isTerminal").GetBoolean());
    }

    [Fact]
    public async Task Invalid_requests_never_reach_python()
    {
        var (client, python) = StubbedPythonHost.Create(factory);

        var responses = new[]
        {
            await client.PostJsonAsync("/api/v1/simulations", """{"resistanceProfile":[0,0,0],"strategy":"ppo"}"""),
            await client.PostJsonAsync("/api/v1/simulations", """{"resistanceProfile":[0,0,0,0,0,0,0],"strategy":"greedy"}"""),
            await client.PostJsonAsync("/api/v1/comparisons", """{"resistanceProfile":[0,0,0,0,0,0,0],"horizon":3}"""),
            await client.PostJsonAsync("/api/v1/profiles/validate", """{"resistanceProfile":[0,0,0,0,0,0,2]}"""),
        };

        Assert.All(responses, response => Assert.Equal(HttpStatusCode.UnprocessableEntity, response.StatusCode));
        Assert.Equal(0, python.CallCount);
    }

    [Fact]
    public async Task Python_failures_become_safe_problems_without_leaking_internals()
    {
        var (client, _) = StubbedPythonHost.Create(factory, (_, _) => Task.FromResult(PythonFixtures.Fixture("simulate_500_internal_error", HttpStatusCode.InternalServerError)));

        var response = await client.PostJsonAsync("/api/v1/simulations", PpoBody);

        await response.ReadProblemAsync(HttpStatusCode.InternalServerError, ErrorCodes.InternalError);
        var text = await response.Content.ReadAsStringAsync();
        Assert.DoesNotContain("d23ddadb-4793-4177-98d6-0f0de69e3da6", text, StringComparison.Ordinal);
        Assert.DoesNotContain("python.test", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Traceback", text, StringComparison.Ordinal);
    }

    [Fact]
    public async Task A_python_comparison_contract_violation_is_a_500_with_no_comparison_body()
    {
        var (client, _) = StubbedPythonHost.Create(factory, (_, _) => Task.FromResult(PythonFixtures.Fixture("compare_500_contract_violation", HttpStatusCode.InternalServerError)));

        var response = await client.PostJsonAsync("/api/v1/comparisons", CompareBody);

        var problem = await response.ReadProblemAsync(HttpStatusCode.InternalServerError, ErrorCodes.ComparisonContractViolation);
        Assert.False(problem.TryGetProperty("ppo", out _));
        Assert.False(problem.TryGetProperty("contract", out _));
    }

    [Fact]
    public async Task An_unavailable_model_is_a_503()
    {
        var (client, _) = StubbedPythonHost.Create(factory, (_, _) => Task.FromResult(PythonFixtures.Fixture("model_503_checkpoint_integrity_failure", HttpStatusCode.ServiceUnavailable)));

        var response = await client.GetAsync("/api/v1/model");

        await response.ReadProblemAsync(HttpStatusCode.ServiceUnavailable, ErrorCodes.ModelUnavailable);
        Assert.DoesNotContain("checkpoint_integrity_failure", await response.Content.ReadAsStringAsync(), StringComparison.Ordinal);
    }

    [Fact]
    public async Task An_unreachable_python_service_is_a_503_problem()
    {
        var (client, _) = StubbedPythonHost.Create(factory, (_, _) => throw new HttpRequestException("Connection refused to python.test:8000"));

        var response = await client.PostJsonAsync("/api/v1/simulations", PpoBody);

        await response.ReadProblemAsync(HttpStatusCode.ServiceUnavailable, ErrorCodes.PythonServiceUnavailable);
        Assert.DoesNotContain("python.test", await response.Content.ReadAsStringAsync(), StringComparison.Ordinal);
    }

    [Fact]
    public async Task A_python_request_that_exceeds_the_timeout_is_a_503_timeout_problem()
    {
        var settings = new Dictionary<string, string?> { ["PythonService:RequestTimeoutSeconds"] = "1" };
        var (client, _) = StubbedPythonHost.Create(factory, async (_, token) =>
        {
            await Task.Delay(Timeout.Infinite, token);
            return new HttpResponseMessage();
        }, settings);

        var response = await client.PostJsonAsync("/api/v1/simulations", PpoBody);

        await response.ReadProblemAsync(HttpStatusCode.ServiceUnavailable, ErrorCodes.PythonServiceTimeout);
    }

    [Fact]
    public async Task A_non_json_python_success_body_is_a_502_invalid_response()
    {
        var (client, _) = StubbedPythonHost.Create(factory, (_, _) => Task.FromResult(PythonFixtures.Respond(HttpStatusCode.OK, "<html>proxy</html>", "text/html")));

        var response = await client.PostJsonAsync("/api/v1/simulations", PpoBody);

        await response.ReadProblemAsync(HttpStatusCode.BadGateway, ErrorCodes.PythonServiceInvalidResponse);
    }

    [Fact]
    public async Task A_python_result_for_a_different_request_is_rejected_not_returned()
    {
        var (client, _) = StubbedPythonHost.Create(factory);

        var response = await client.PostJsonAsync("/api/v1/simulations", """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"ppo","environmentSeed":5}""");

        Assert.NotEqual(HttpStatusCode.Created, response.StatusCode);
        Assert.StartsWith("application/problem+json", response.Content.Headers.ContentType!.MediaType, StringComparison.Ordinal);
    }

    [Fact]
    public async Task A_python_metric_set_that_differs_from_the_catalogue_is_rejected()
    {
        var body = PythonFixtures.Mutate("simulate_200_ppo", node => node["metric_definitions"]!.AsObject().Remove("unsupported_step_count"));
        var (client, _) = StubbedPythonHost.Create(factory, (_, _) => Task.FromResult(PythonFixtures.Respond(HttpStatusCode.OK, body)));

        var response = await client.PostJsonAsync("/api/v1/simulations", PpoBody);

        await response.ReadProblemAsync(HttpStatusCode.BadGateway, ErrorCodes.PythonServiceInvalidResponse);
    }

    [Fact]
    public async Task Client_cancellation_aborts_the_python_request()
    {
        var observed = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        var (client, _) = StubbedPythonHost.Create(factory, async (_, token) =>
        {
            token.Register(() => observed.TrySetResult(true));
            await Task.Delay(Timeout.Infinite, token);
            return new HttpResponseMessage();
        });
        using var cancellation = new CancellationTokenSource();

        var pending = client.PostAsync("/api/v1/simulations", new StringContent(PpoBody, System.Text.Encoding.UTF8, "application/json"), cancellation.Token);
        await Task.Delay(300);
        await cancellation.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => pending);
        Assert.True(await Task.WhenAny(observed.Task, Task.Delay(TimeSpan.FromSeconds(5))) == observed.Task, "Python never saw the cancellation.");
    }

    [Fact]
    public async Task A_reachable_service_without_a_verified_model_reports_a_stable_model_code_only()
    {
        var (client, _) = StubbedPythonHost.Create(factory, (_, _) => Task.FromResult(PythonFixtures.Fixture("health_503_model_unavailable", HttpStatusCode.ServiceUnavailable)));

        var response = await client.GetAsync("/api/v1/health");

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        var text = await response.Content.ReadAsStringAsync();
        var components = System.Text.Json.JsonDocument.Parse(text).RootElement.GetProperty("components").EnumerateArray()
            .ToDictionary(item => item.GetProperty("name").GetString()!, item => (item.GetProperty("status").GetString(), item.GetProperty("detail").GetString()));
        Assert.Equal(("healthy", null), components["pythonService"]);
        Assert.Equal(("unhealthy", "model_unavailable"), components["model"]);
        Assert.DoesNotContain("python.test", text, StringComparison.Ordinal);
    }

    [Fact]
    public async Task An_unreachable_python_service_makes_readiness_fail_but_not_liveness()
    {
        var (client, python) = StubbedPythonHost.Create(factory, (_, _) => throw new HttpRequestException("refused"));

        var live = await client.GetAsync("/api/v1/health/live");
        var ready = await client.GetAsync("/api/v1/health");

        Assert.Equal(HttpStatusCode.OK, live.StatusCode);
        Assert.Equal(HttpStatusCode.ServiceUnavailable, ready.StatusCode);
        Assert.Equal(1, python.CallCount);
    }
}
