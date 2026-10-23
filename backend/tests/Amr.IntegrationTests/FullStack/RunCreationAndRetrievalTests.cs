using System.Net;
using System.Text.Json;
using System.Text.Json.Nodes;
using Amr.Application.Errors;
using Amr.Application.Metrics;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.EntityFrameworkCore;

namespace Amr.IntegrationTests.FullStack;

/// <summary>
/// The full stack against a real PostgreSQL database: stubbed Python network, real controllers, services, repository and
/// migrations. Needs AMR_TEST_POSTGRES; skipped (and reported as skipped) without it.
/// </summary>
public class RunCreationAndRetrievalTests(AmrApiFactory factory, PostgresDatabaseFixture db)
    : IClassFixture<AmrApiFactory>, IClassFixture<PostgresDatabaseFixture>
{
    private const string PpoBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"ppo","environmentSeed":100001}""";
    private const string BaselineBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"random_susceptible_baseline","environmentSeed":100001,"policySeed":900001}""";
    private const string TerminalBody = """{"resistanceProfile":[1,1,1,1,1,1,1],"strategy":"ppo","environmentSeed":1}""";
    private const string CompareBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"environmentSeed":100001,"policySeed":900001}""";

    private (HttpClient Client, StubHandler Python) Host(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>>? respond = null) =>
        StubbedPythonHost.Create(factory, respond, databaseConnectionString: db.ConnectionString);

    private async Task<(int Runs, int Models, int Strategies, int Steps)> CountsAsync()
    {
        await using var context = db.CreateContext();
        return (await context.ExperimentRuns.CountAsync(), await context.ModelVersions.CountAsync(), await context.StrategyRuns.CountAsync(), await context.StepTraces.CountAsync());
    }

    private static void AssertSameJson(JsonElement expected, JsonElement actual) =>
        Assert.True(JsonNode.DeepEquals(JsonNode.Parse(expected.GetRawText()), JsonNode.Parse(actual.GetRawText())), $"Expected {expected.GetRawText()}{Environment.NewLine}Actual   {actual.GetRawText()}");

    [PostgresTheory]
    [InlineData("/api/v1/simulations", PpoBody)]
    [InlineData("/api/v1/simulations", BaselineBody)]
    [InlineData("/api/v1/simulations", TerminalBody)]
    [InlineData("/api/v1/comparisons", CompareBody)]
    public async Task A_created_run_is_201_persisted_and_retrievable_exactly_as_returned(string route, string body)
    {
        var (client, _) = Host();

        var created = await client.PostJsonAsync(route, body);

        Assert.Equal(HttpStatusCode.Created, created.StatusCode);
        var returned = await created.ReadJsonAsync();
        var id = returned.GetProperty("id").GetGuid();
        Assert.True(returned.GetProperty("isPersisted").GetBoolean());
        Assert.Equal($"{route}/{id}", created.Headers.Location!.AbsolutePath);

        var fetched = await client.GetAsync(created.Headers.Location);

        Assert.Equal(HttpStatusCode.OK, fetched.StatusCode);
        AssertSameJson(returned, await fetched.ReadJsonAsync());
    }

    [PostgresFact]
    public async Task The_status_id_and_flag_agree_with_what_was_actually_stored()
    {
        var (client, _) = Host();
        var before = await CountsAsync();

        var created = await client.PostJsonAsync("/api/v1/simulations", PpoBody);

        var returned = await created.ReadJsonAsync();
        var after = await CountsAsync();
        Assert.Equal((before.Runs + 1, before.Strategies + 1), (after.Runs, after.Strategies));
        await using var context = db.CreateContext();
        var row = await context.ExperimentRuns.SingleAsync(run => run.Id == returned.GetProperty("id").GetGuid());
        Assert.True(row.RecordedAtUtc >= row.CreatedAtUtc.AddDays(-1));
        Assert.Equal(Domain.Enums.RunStatus.Completed, row.Status);
        Assert.True(returned.GetProperty("isPersisted").GetBoolean());
    }

    [PostgresFact]
    public async Task A_simulation_id_is_not_a_comparison_id_and_the_reverse()
    {
        var (client, _) = Host();
        var simulationId = (await (await client.PostJsonAsync("/api/v1/simulations", PpoBody)).ReadJsonAsync()).GetProperty("id").GetGuid();
        var comparisonId = (await (await client.PostJsonAsync("/api/v1/comparisons", CompareBody)).ReadJsonAsync()).GetProperty("id").GetGuid();

        await (await client.GetAsync($"/api/v1/comparisons/{simulationId}")).ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.NotFound);
        await (await client.GetAsync($"/api/v1/simulations/{comparisonId}")).ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.NotFound);
        await (await client.GetAsync($"/api/v1/simulations/{Guid.NewGuid()}")).ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.NotFound);
    }

    [PostgresFact]
    public async Task Recommendations_exist_only_for_ppo_simulations()
    {
        var (client, _) = Host();
        var ppoId = (await (await client.PostJsonAsync("/api/v1/simulations", PpoBody)).ReadJsonAsync()).GetProperty("id").GetGuid();
        var baselineId = (await (await client.PostJsonAsync("/api/v1/simulations", BaselineBody)).ReadJsonAsync()).GetProperty("id").GetGuid();
        var comparisonId = (await (await client.PostJsonAsync("/api/v1/comparisons", CompareBody)).ReadJsonAsync()).GetProperty("id").GetGuid();

        var found = await client.GetAsync($"/api/v1/recommendations/{ppoId}");

        Assert.Equal(HttpStatusCode.OK, found.StatusCode);
        var recommendation = await found.ReadJsonAsync();
        Assert.Equal(ppoId, recommendation.GetProperty("simulationId").GetGuid());
        Assert.Equal("ppo", recommendation.GetProperty("strategy").GetString());
        var stored = await (await client.GetAsync($"/api/v1/simulations/{ppoId}")).ReadJsonAsync();
        AssertSameJson(stored.GetProperty("result").GetProperty("steps"), recommendation.GetProperty("steps"));
        foreach (var other in new[] { baselineId, comparisonId, Guid.NewGuid() })
        {
            await (await client.GetAsync($"/api/v1/recommendations/{other}")).ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.RecommendationNotFound);
        }

        await (await client.GetAsync("/api/v1/recommendations/not-a-guid")).ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.NotFound);
    }

    [PostgresFact]
    public async Task A_susceptible_drug_without_candidate_data_stays_unsupported_through_storage_and_every_endpoint()
    {
        var (client, _) = Host();
        var created = await (await client.PostJsonAsync("/api/v1/simulations", PpoBody)).ReadJsonAsync();
        var id = created.GetProperty("id").GetGuid();

        var fetched = await (await client.GetAsync($"/api/v1/simulations/{id}")).ReadJsonAsync();
        var recommendation = await (await client.GetAsync($"/api/v1/recommendations/{id}")).ReadJsonAsync();

        foreach (var steps in new[] { created.GetProperty("result").GetProperty("steps"), fetched.GetProperty("result").GetProperty("steps"), recommendation.GetProperty("steps") })
        {
            var unsupported = steps.EnumerateArray().Where(step => step.GetProperty("transitionStatus").GetString() == "unsupported_no_candidate").ToList();
            Assert.NotEmpty(unsupported);
            Assert.All(unsupported, step =>
            {
                Assert.True(step.GetProperty("selectedDrugSusceptible").GetBoolean());
                Assert.False(step.GetProperty("hasCandidateTransition").GetBoolean());
                Assert.Equal(JsonValueKind.Null, step.GetProperty("selectedOutcome").ValueKind);
                Assert.Equal(0, step.GetProperty("candidateTransitions").GetArrayLength());
                Assert.Equal(step.GetProperty("resistanceProfileBefore").GetRawText(), step.GetProperty("resistanceProfileAfter").GetRawText());
                Assert.False(step.TryGetProperty("effective", out _));
            });
            Assert.Equal(
                unsupported.Count,
                fetched.GetProperty("result").GetProperty("metrics").GetProperty("unsupportedStepCount").GetInt32());
        }

        await using var context = db.CreateContext();
        var rows = await context.StepTraces.Where(step => step.StrategyRun.ExperimentRunId == id && step.TransitionStatus == "unsupported_no_candidate").ToListAsync();
        Assert.NotEmpty(rows);
        Assert.All(rows, row => Assert.True(row.SelectedDrugSusceptible && !row.HasCandidateTransition && row.SelectedOutcome is null));
    }

    [PostgresFact]
    public async Task Metric_definitions_are_canonical_and_survive_storage_unchanged()
    {
        var (client, _) = Host();
        var created = await (await client.PostJsonAsync("/api/v1/simulations", PpoBody)).ReadJsonAsync();
        var id = created.GetProperty("id").GetGuid();
        var fetched = await (await client.GetAsync($"/api/v1/simulations/{id}")).ReadJsonAsync();
        var python = JsonNode.Parse(PythonFixtures.Read("simulate_200_ppo"))!["metric_definitions"]!.AsObject();

        foreach (var response in new[] { created, fetched })
        {
            var definitions = response.GetProperty("metricDefinitions");
            var metrics = response.GetProperty("result").GetProperty("metrics");
            Assert.Equal(
                metrics.EnumerateObject().Select(property => property.Name).Order(StringComparer.Ordinal),
                definitions.EnumerateObject().Select(property => property.Name).Order(StringComparer.Ordinal));
            foreach (var entry in MetricCatalogue.Entries)
            {
                var definition = definitions.GetProperty(JsonNamingPolicy.CamelCase.ConvertName(entry.PublicName));
                Assert.Equal(python[entry.PythonKey]!.GetValue<string>(), definition.GetProperty("definition").GetString());
                Assert.Equal(JsonNamingPolicy.SnakeCaseLower.ConvertName(entry.Kind.ToString()), definition.GetProperty("kind").GetString());
                Assert.Equal(entry.Unit, definition.GetProperty("unit").GetString());
                Assert.Equal(entry.Aggregation, definition.GetProperty("aggregation").GetString());
            }
        }

        AssertSameJson(created.GetProperty("metricDefinitions"), fetched.GetProperty("metricDefinitions"));
    }

    [PostgresFact]
    public async Task A_comparison_stores_both_strategies_with_the_contract_and_every_step_in_order()
    {
        var (client, _) = Host();
        var created = await (await client.PostJsonAsync("/api/v1/comparisons", CompareBody)).ReadJsonAsync();
        var id = created.GetProperty("id").GetGuid();

        await using var context = db.CreateContext();
        var strategies = await context.StrategyRuns.Where(strategy => strategy.ExperimentRunId == id).Include(strategy => strategy.StepTraces).ToListAsync();

        Assert.Equal(
            new[] { Domain.Enums.StrategyKind.Ppo, Domain.Enums.StrategyKind.RandomSusceptibleBaseline, Domain.Enums.StrategyKind.Dqn },
            strategies.Select(strategy => strategy.Strategy).Order());
        foreach (var strategy in strategies)
        {
            Assert.Equal(strategy.TreatmentSteps, strategy.StepTraces.Count);
            Assert.Equal(Enumerable.Range(0, strategy.TreatmentSteps), strategy.StepTraces.Select(step => step.StepIndex).Order());
        }

        var contract = created.GetProperty("contract");
        Assert.True(contract.GetProperty("verified").GetBoolean());
        Assert.False(contract.GetProperty("transitionOutcomesGuaranteedIdentical").GetBoolean());
    }

    [PostgresFact]
    public async Task Concurrent_creations_all_succeed_with_distinct_ids_and_share_one_model_version()
    {
        var (client, _) = Host();
        var before = await CountsAsync();

        var responses = await Task.WhenAll(Enumerable.Range(0, 16).Select(index =>
            client.PostJsonAsync(index % 2 == 0 ? "/api/v1/simulations" : "/api/v1/comparisons", index % 2 == 0 ? PpoBody : CompareBody)));

        Assert.All(responses, response => Assert.Equal(HttpStatusCode.Created, response.StatusCode));
        var ids = (await Task.WhenAll(responses.Select(async response => (await response.ReadJsonAsync()).GetProperty("id").GetGuid()))).ToList();
        Assert.Equal(16, ids.Distinct().Count());
        var after = await CountsAsync();
        Assert.Equal(before.Runs + 16, after.Runs);
        Assert.InRange(after.Models, Math.Max(before.Models, 1), before.Models + 1);
        Assert.Equal(before.Strategies + (8 * 1) + (8 * 3), after.Strategies);
    }

    [PostgresFact]
    public async Task A_different_checkpoint_gets_its_own_model_version()
    {
        var (client, _) = Host();
        var same = await client.PostJsonAsync("/api/v1/simulations", PpoBody);
        var before = await CountsAsync();
        var other = new string('a', 64);
        var (otherClient, _) = Host(StubbedPythonHost.Serving("simulate_200_ppo", (node, _) => node["provenance"]!["checkpoint_sha256"] = other));

        var response = await otherClient.PostJsonAsync("/api/v1/simulations", PpoBody);

        Assert.Equal(HttpStatusCode.Created, same.StatusCode);
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        Assert.Equal(before.Models + 1, (await CountsAsync()).Models);
        var fetched = await (await client.GetAsync(response.Headers.Location)).ReadJsonAsync();
        Assert.Equal(other, fetched.GetProperty("provenance").GetProperty("checkpointSha256").GetString());
    }

    [PostgresFact]
    public async Task A_duplicate_run_id_is_a_persistence_failure_that_never_overwrites_or_claims_success()
    {
        var fixedId = Guid.NewGuid();
        var (client, python) = Host(StubbedPythonHost.Serving("simulate_200_ppo", (node, _) => node["run_id"] = fixedId.ToString()));
        var first = await client.PostJsonAsync("/api/v1/simulations", PpoBody);
        var firstBody = await first.ReadJsonAsync();
        var before = await CountsAsync();

        var second = await client.PostJsonAsync("/api/v1/simulations", PpoBody);

        Assert.Equal(HttpStatusCode.Created, first.StatusCode);
        var problem = await second.ReadProblemAsync(HttpStatusCode.InternalServerError, ErrorCodes.PersistenceFailed);
        Assert.Contains("No record exists", problem.GetProperty("detail").GetString(), StringComparison.Ordinal);
        Assert.False(problem.TryGetProperty("isPersisted", out _));
        Assert.Equal(2, python.CallCount);
        Assert.Equal(before, await CountsAsync());
        AssertSameJson(firstBody, await (await client.GetAsync($"/api/v1/simulations/{fixedId}")).ReadJsonAsync());
    }

    [PostgresFact]
    public async Task A_failed_save_rolls_back_everything_including_a_new_model_version()
    {
        var fixedId = Guid.NewGuid();
        var (client, _) = Host(StubbedPythonHost.Serving("simulate_200_ppo", (node, call) =>
        {
            node["run_id"] = fixedId.ToString();
            if (call > 1)
            {
                node["provenance"]!["checkpoint_sha256"] = new string('b', 64);
            }
        }));
        await client.PostJsonAsync("/api/v1/simulations", PpoBody);
        var before = await CountsAsync();

        var second = await client.PostJsonAsync("/api/v1/simulations", PpoBody);

        await second.ReadProblemAsync(HttpStatusCode.InternalServerError, ErrorCodes.PersistenceFailed);
        Assert.Equal(before, await CountsAsync());
    }

    [PostgresTheory]
    [InlineData("verified")]
    [InlineData("transition_outcomes_guaranteed_identical")]
    [InlineData("request_mismatch")]
    public async Task A_comparison_that_breaks_its_contract_is_never_persisted(string violation)
    {
        var (client, _) = Host(StubbedPythonHost.Serving("compare_200", (node, _) =>
        {
            switch (violation)
            {
                case "verified":
                    node["comparison_contract"]!["verified"] = false;
                    break;
                case "transition_outcomes_guaranteed_identical":
                    node["comparison_contract"]!["transition_outcomes_guaranteed_identical"] = true;
                    break;
                default:
                    node["greedy"]!["environment_seed"] = 5;
                    break;
            }
        }));
        var before = await CountsAsync();

        var response = await client.PostJsonAsync("/api/v1/comparisons", CompareBody);

        await response.ReadProblemAsync(HttpStatusCode.InternalServerError, ErrorCodes.ComparisonContractViolation);
        Assert.Equal(before, await CountsAsync());
    }

    [PostgresFact]
    public async Task Upstream_failures_and_invalid_responses_are_never_persisted()
    {
        var before = await CountsAsync();
        var (failing, _) = Host((_, _) => Task.FromResult(PythonFixtures.Fixture("simulate_500_internal_error", HttpStatusCode.InternalServerError)));
        var (mismatched, _) = Host(StubbedPythonHost.Serving("simulate_200_ppo", (node, _) => node["result"]!["strategy"] = "greedy"));

        await (await failing.PostJsonAsync("/api/v1/simulations", PpoBody)).ReadProblemAsync(HttpStatusCode.InternalServerError, ErrorCodes.InternalError);
        await (await mismatched.PostJsonAsync("/api/v1/simulations", PpoBody)).ReadProblemAsync(HttpStatusCode.BadGateway, ErrorCodes.PythonServiceInvalidResponse);

        Assert.Equal(before, await CountsAsync());
    }

    [PostgresFact]
    public async Task Readiness_is_healthy_only_when_python_the_model_and_the_migrated_database_are_all_healthy()
    {
        var (client, _) = Host();

        var response = await client.GetAsync("/api/v1/health");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var components = (await response.ReadJsonAsync()).GetProperty("components").EnumerateArray().Select(item => (item.GetProperty("name").GetString()!, item.GetProperty("status").GetString()!)).ToList();
        Assert.Equal(new[] { ("api", "healthy"), ("pythonService", "healthy"), ("model", "healthy"), ("database", "healthy") }, components);
    }
}
