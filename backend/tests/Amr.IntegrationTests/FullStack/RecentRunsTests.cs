using System.Net;
using System.Text.Json;
using Amr.Application.Errors;
using Amr.IntegrationTests.Infrastructure;

namespace Amr.IntegrationTests.FullStack;

/// <summary>Seeds five runs once: ids and times are chosen to force ordering, a created-at tie and paging.</summary>
public sealed class RecentRunsFixture : PostgresDatabaseFixture
{
    public static readonly Guid OldestSimulation = Guid.Parse("00000000-0000-0000-0000-0000000000a1");
    public static readonly Guid MiddleComparison = Guid.Parse("00000000-0000-0000-0000-0000000000b1");
    public static readonly Guid MiddleBaseline = Guid.Parse("00000000-0000-0000-0000-0000000000c1");
    public static readonly Guid TieLowId = Guid.Parse("00000000-0000-0000-0000-0000000000d1");
    public static readonly Guid TieHighId = Guid.Parse("00000000-0000-0000-0000-0000000000e1");

    public override async Task InitializeAsync()
    {
        await base.InitializeAsync();
        if (string.IsNullOrEmpty(ConnectionString))
        {
            return;
        }

        using var factory = new AmrApiFactory();
        const string ppo = """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"ppo","environmentSeed":100001}""";
        const string baseline = """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"random_susceptible_baseline","environmentSeed":100001,"policySeed":900001}""";
        const string compare = """{"resistanceProfile":[0,1,0,0,0,0,0],"environmentSeed":100001,"policySeed":900001}""";
        await Seed(factory, "/api/v1/simulations", ppo, "simulate_200_ppo", OldestSimulation, "2026-01-01T10:00:00+00:00");
        await Seed(factory, "/api/v1/comparisons", compare, "compare_200", MiddleComparison, "2026-01-03T10:00:00+00:00");
        await Seed(factory, "/api/v1/simulations", baseline, "simulate_200_baseline", MiddleBaseline, "2026-01-02T10:00:00+00:00");
        await Seed(factory, "/api/v1/simulations", ppo, "simulate_200_ppo", TieLowId, "2026-01-04T10:00:00+00:00");
        await Seed(factory, "/api/v1/comparisons", compare, "compare_200", TieHighId, "2026-01-04T10:00:00+00:00");
    }

    private async Task Seed(AmrApiFactory factory, string route, string body, string fixture, Guid id, string createdAt)
    {
        var (client, _) = StubbedPythonHost.Create(
            factory,
            StubbedPythonHost.Serving(fixture, (node, _) =>
            {
                node["run_id"] = id.ToString();
                node["created_at_utc"] = createdAt;
            }),
            databaseConnectionString: ConnectionString);
        var response = await client.PostJsonAsync(route, body);
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
    }
}

/// <summary>Recent-run listing against real storage.</summary>
public class RecentRunsTests(AmrApiFactory factory, RecentRunsFixture db)
    : IClassFixture<AmrApiFactory>, IClassFixture<RecentRunsFixture>
{
    private static readonly Guid OldestSimulation = RecentRunsFixture.OldestSimulation;
    private static readonly Guid MiddleComparison = RecentRunsFixture.MiddleComparison;
    private static readonly Guid MiddleBaseline = RecentRunsFixture.MiddleBaseline;
    private static readonly Guid TieLowId = RecentRunsFixture.TieLowId;
    private static readonly Guid TieHighId = RecentRunsFixture.TieHighId;

    private HttpClient? _clientInstance;

    private HttpClient Client => _clientInstance ??= StubbedPythonHost.Create(factory, databaseConnectionString: db.ConnectionString).Client;

    private async Task<JsonElement> RecentAsync(string query = "") => await (await Client.GetAsync($"/api/v1/simulations/recent{query}")).ReadJsonAsync();

    private static Guid[] Ids(JsonElement page) => page.GetProperty("items").EnumerateArray().Select(item => item.GetProperty("id").GetGuid()).ToArray();

    [PostgresFact]
    public async Task Runs_are_listed_newest_first_with_ties_broken_by_id_descending_and_both_kinds_included()
    {
        var page = await RecentAsync();

        Assert.Equal(new[] { TieHighId, TieLowId, MiddleComparison, MiddleBaseline, OldestSimulation }, Ids(page));
        Assert.Equal((1, 20, 5), (page.GetProperty("page").GetInt32(), page.GetProperty("pageSize").GetInt32(), page.GetProperty("totalCount").GetInt32()));
    }

    [PostgresFact]
    public async Task Pages_do_not_overlap_or_skip_and_a_page_past_the_end_is_empty()
    {
        var first = await RecentAsync("?page=1&pageSize=2");
        var second = await RecentAsync("?page=2&pageSize=2");
        var third = await RecentAsync("?page=3&pageSize=2");
        var beyond = await RecentAsync("?page=4&pageSize=2");

        Assert.Equal(new[] { TieHighId, TieLowId }, Ids(first));
        Assert.Equal(new[] { MiddleComparison, MiddleBaseline }, Ids(second));
        Assert.Equal(new[] { OldestSimulation }, Ids(third));
        Assert.Empty(Ids(beyond));
        Assert.All(new[] { first, second, third, beyond }, page => Assert.Equal(5, page.GetProperty("totalCount").GetInt32()));
    }

    [PostgresFact]
    public async Task A_huge_page_number_is_an_empty_page_not_an_overflow()
    {
        var page = await RecentAsync($"?page={int.MaxValue}&pageSize=50");

        Assert.Empty(Ids(page));
        Assert.Equal(5, page.GetProperty("totalCount").GetInt32());
    }

    [PostgresFact]
    public async Task Rows_describe_their_kind_strategies_model_and_stored_metrics()
    {
        var page = await RecentAsync();
        var items = page.GetProperty("items").EnumerateArray().ToDictionary(item => item.GetProperty("id").GetGuid());

        var simulation = items[OldestSimulation];
        Assert.Equal("simulation", simulation.GetProperty("kind").GetString());
        Assert.Equal(new[] { "ppo" }, simulation.GetProperty("strategies").EnumerateArray().Select(strategy => strategy.GetProperty("strategy").GetString()));
        Assert.Equal("ppo_seed_12000", simulation.GetProperty("modelId").GetString());
        Assert.Equal("completed", simulation.GetProperty("status").GetString());
        Assert.Equal("2026-01-01T10:00:00+00:00", simulation.GetProperty("createdAtUtc").GetString());
        Assert.Equal(new[] { 0, 1, 0, 0, 0, 0, 0 }, simulation.GetProperty("initialProfile").EnumerateArray().Select(value => value.GetInt32()));

        var comparison = items[MiddleComparison];
        Assert.Equal("comparison", comparison.GetProperty("kind").GetString());
        Assert.Equal(
            new[] { "ppo", "random_susceptible_baseline" },
            comparison.GetProperty("strategies").EnumerateArray().Select(strategy => strategy.GetProperty("strategy").GetString()));

        var stored = await (await Client.GetAsync($"/api/v1/comparisons/{MiddleComparison}")).ReadJsonAsync();
        var summarized = comparison.GetProperty("strategies")[0];
        var metrics = stored.GetProperty("ppo").GetProperty("metrics");
        Assert.Equal(metrics.GetProperty("cumulativeResistanceBurden").GetDouble(), summarized.GetProperty("cumulativeResistanceBurden").GetDouble());
        Assert.Equal(metrics.GetProperty("finalResistantCount").GetInt32(), summarized.GetProperty("finalResistantCount").GetInt32());
        Assert.Equal(stored.GetProperty("ppo").GetProperty("terminationReason").GetString(), summarized.GetProperty("terminationReason").GetString());
    }

    [PostgresTheory]
    [InlineData("?page=0")]
    [InlineData("?pageSize=0")]
    [InlineData("?pageSize=51")]
    public async Task Out_of_range_paging_is_still_a_422(string query)
    {
        var response = await Client.GetAsync($"/api/v1/simulations/recent{query}");

        await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
    }
}
