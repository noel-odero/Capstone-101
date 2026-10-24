using System.Net;
using System.Text.Json;
using System.Text.Json.Nodes;
using Amr.Application.Interfaces.Clients;
using Amr.Application.Metrics;
using Amr.Application.PythonContracts;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Amr.IntegrationTests;

/// <summary>Needs both a live Python service (AMR_PYTHON_URL) and a PostgreSQL server (AMR_TEST_POSTGRES). In the live CI job a missing one is a failure.</summary>
public sealed class LiveDatabaseFactAttribute : FactAttribute
{
    public LiveDatabaseFactAttribute()
    {
        var missing = Environment.GetEnvironmentVariable(LiveFactAttribute.UrlVariable) is null || PostgresDatabaseFactMissing;
        if (missing && !LiveFactAttribute.Required)
        {
            Skip = $"Set {LiveFactAttribute.UrlVariable} and {PostgresDatabaseFixture.AdminVariable} to run the live end-to-end tests.";
        }
    }

    private static bool PostgresDatabaseFactMissing => PostgresDatabaseFixture.AdminConnectionString is null;
}

/// <summary>The real Python service through the real API and a real database: the contract as it is today, not as the fixtures remember it.</summary>
public sealed class LiveEndToEndTests : IAsyncLifetime, IDisposable
{
    private TempDatabase? _database;
    private AmrApiFactory? _factory;
    private HttpClient _client = null!;
    private IPythonServiceClient _python = null!;

    public async Task InitializeAsync()
    {
        if (Environment.GetEnvironmentVariable(LiveFactAttribute.UrlVariable) is null || PostgresDatabaseFixture.AdminConnectionString is null)
        {
            if (LiveFactAttribute.Required)
            {
                throw new InvalidOperationException($"{LiveFactAttribute.RequireVariable} is true but {LiveFactAttribute.UrlVariable} or {PostgresDatabaseFixture.AdminVariable} is not set.");
            }

            return;
        }

        _database = await TempDatabase.CreateAsync();
        await using (var context = _database.CreateContext())
        {
            await Microsoft.EntityFrameworkCore.RelationalDatabaseFacadeExtensions.MigrateAsync(context.Database);
        }

        _factory = new AmrApiFactory();
        var configured = _factory.WithWebHostBuilder(builder => builder.ConfigureAppConfiguration((_, configuration) =>
            configuration.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["PythonService:BaseUrl"] = LiveFactAttribute.Url!,
                ["ConnectionStrings:Amr"] = _database.ConnectionString,
            })));
        _client = configured.CreateClient();
        _python = configured.Services.GetRequiredService<IPythonServiceClient>();
    }

    public void Dispose() => _factory?.Dispose();

    public async Task DisposeAsync()
    {
        if (_database is not null)
        {
            await _database.DisposeAsync();
        }
    }

    [LiveDatabaseFact]
    public async Task Readiness_is_healthy_for_python_the_model_and_the_migrated_database()
    {
        var response = await _client.GetAsync("/api/v1/health");

        Assert.True(response.StatusCode == HttpStatusCode.OK, await response.Content.ReadAsStringAsync());
        var components = (await response.ReadJsonAsync()).GetProperty("components").EnumerateArray().Select(item => item.GetProperty("name").GetString()).ToList();
        Assert.Equal(new[] { "api", "pythonService", "model", "database" }, components);
    }

    [LiveDatabaseFact]
    public async Task A_live_simulation_is_stored_and_retrieved_identically_with_the_live_metric_definitions()
    {
        var created = await _client.PostJsonAsync("/api/v1/simulations", """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"ppo","environmentSeed":100001}""");

        Assert.Equal(HttpStatusCode.Created, created.StatusCode);
        var returned = await created.ReadJsonAsync();
        Assert.True(returned.GetProperty("isPersisted").GetBoolean());
        var fetched = await (await _client.GetAsync(created.Headers.Location)).ReadJsonAsync();
        Assert.True(JsonNode.DeepEquals(JsonNode.Parse(returned.GetRawText()), JsonNode.Parse(fetched.GetRawText())));

        var live = (await _python.SimulateAsync(new PythonSimulateRequest([0, 1, 0, 0, 0, 0, 0], "ppo", 100001, null), CancellationToken.None)).MetricDefinitions;
        foreach (var entry in MetricCatalogue.Entries)
        {
            Assert.Equal(live[entry.PythonKey], returned.GetProperty("metricDefinitions").GetProperty(JsonNamingPolicy.CamelCase.ConvertName(entry.PublicName)).GetProperty("definition").GetString());
        }
    }

    [LiveDatabaseFact]
    public async Task The_checked_in_fixtures_still_carry_the_live_metric_definitions_and_metric_names()
    {
        var live = (await _python.SimulateAsync(new PythonSimulateRequest([0, 1, 0, 0, 0, 0, 0], "ppo", 100001, null), CancellationToken.None)).MetricDefinitions;
        var fixture = JsonNode.Parse(PythonFixtures.Read("simulate_200_ppo"))!["metric_definitions"]!.AsObject().ToDictionary(pair => pair.Key, pair => pair.Value!.GetValue<string>());

        Assert.Equal(live.OrderBy(pair => pair.Key, StringComparer.Ordinal), fixture.OrderBy(pair => pair.Key, StringComparer.Ordinal));
    }

    [LiveDatabaseFact]
    public async Task A_live_susceptible_drug_without_transition_data_is_unsupported_not_effective_through_storage()
    {
        var created = await (await _client.PostJsonAsync("/api/v1/simulations", """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"ppo","environmentSeed":100001}""")).ReadJsonAsync();
        var id = created.GetProperty("id").GetGuid();

        var fetched = await (await _client.GetAsync($"/api/v1/simulations/{id}")).ReadJsonAsync();

        var steps = fetched.GetProperty("result").GetProperty("steps").EnumerateArray().ToList();
        var unsupported = steps.Where(step => step.GetProperty("transitionStatus").GetString() == "unsupported_no_candidate").ToList();
        Assert.NotEmpty(unsupported);
        Assert.All(unsupported, step =>
        {
            Assert.True(step.GetProperty("selectedDrugSusceptible").GetBoolean());
            Assert.False(step.GetProperty("hasCandidateTransition").GetBoolean());
            Assert.Equal(JsonValueKind.Null, step.GetProperty("selectedOutcome").ValueKind);
        });
        Assert.Equal(unsupported.Count, fetched.GetProperty("result").GetProperty("metrics").GetProperty("unsupportedStepCount").GetInt32());
    }

    [LiveDatabaseFact]
    public async Task A_live_comparison_is_verified_stored_and_listed_and_a_live_baseline_has_no_recommendation()
    {
        var comparison = await _client.PostJsonAsync("/api/v1/comparisons", """{"resistanceProfile":[0,1,0,0,0,0,0],"environmentSeed":100001,"policySeed":900001}""");
        var baseline = await _client.PostJsonAsync("/api/v1/simulations", """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"random_susceptible_baseline","environmentSeed":100001,"policySeed":900001}""");

        Assert.Equal(HttpStatusCode.Created, comparison.StatusCode);
        Assert.Equal(HttpStatusCode.Created, baseline.StatusCode);
        var body = await comparison.ReadJsonAsync();
        Assert.True(body.GetProperty("contract").GetProperty("verified").GetBoolean());
        Assert.Equal("dqn", body.GetProperty("dqn").GetProperty("strategy").GetString());
        Assert.Equal("dqn_public_v2_seed_15000", body.GetProperty("dqn").GetProperty("model").GetProperty("modelId").GetString());
        Assert.Equal("ppo_public_v2_seed_19000", body.GetProperty("ppo").GetProperty("model").GetProperty("modelId").GetString());
        var fetched = await (await _client.GetAsync(comparison.Headers.Location)).ReadJsonAsync();
        Assert.True(JsonNode.DeepEquals(JsonNode.Parse(body.GetRawText()), JsonNode.Parse(fetched.GetRawText())));
        var recent = await (await _client.GetAsync("/api/v1/simulations/recent")).ReadJsonAsync();
        var ids = recent.GetProperty("items").EnumerateArray().Select(item => item.GetProperty("id").GetGuid()).ToList();
        Assert.Contains(body.GetProperty("id").GetGuid(), ids);
        var baselineId = (await baseline.ReadJsonAsync()).GetProperty("id").GetGuid();
        await (await _client.GetAsync($"/api/v1/recommendations/{baselineId}")).ReadProblemAsync(HttpStatusCode.NotFound, "recommendation_not_found");
    }
}
