using System.Net;
using System.Text.Json;
using Amr.Application.Interfaces.Clients;
using Amr.Infrastructure.Persistence;
using Amr.Infrastructure.Python;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Amr.IntegrationTests.FullStack;

/// <summary>
/// Stored runs belong to the user who created them. Real controllers, services, repository and PostgreSQL; the identities are
/// deterministic test users. Needs AMR_TEST_POSTGRES.
/// </summary>
public class OwnershipTests(AmrApiFactory factory, PostgresDatabaseFixture db) : IClassFixture<AmrApiFactory>, IClassFixture<PostgresDatabaseFixture>
{
    private const string CompareBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"environmentSeed":100001,"policySeed":900001}""";
    private const string PpoBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"ppo","environmentSeed":100001}""";

    private WebApplicationFactory<Program> Host() =>
        factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureAppConfiguration((_, configuration) =>
                configuration.AddInMemoryCollection(new Dictionary<string, string?> { ["ConnectionStrings:Amr"] = db.ConnectionString }));
            builder.ConfigureTestServices(services =>
                services.AddHttpClient<IPythonServiceClient, PythonServiceClient>().ConfigurePrimaryHttpMessageHandler(() => new StubHandler(StubbedPythonHost.Route)));
        });

    private static HttpClient ClientFor(WebApplicationFactory<Program> host, string user)
    {
        var client = host.CreateClient();
        client.DefaultRequestHeaders.Remove(TestAuthHandler.UserHeader);
        client.DefaultRequestHeaders.Add(TestAuthHandler.UserHeader, user);
        return client;
    }

    private static async Task<Guid> CreateAsync(HttpClient client, string route, string body)
    {
        var response = await client.PostJsonAsync(route, body);
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        return (await response.ReadJsonAsync()).GetProperty("id").GetGuid();
    }

    private static async Task<JsonElement> RecentAsync(HttpClient client) =>
        await (await client.GetAsync("/api/v1/simulations/recent?page=1&pageSize=50")).ReadJsonAsync();

    [PostgresFact]
    public async Task A_run_is_stored_under_its_creator_and_only_the_creator_can_read_it()
    {
        var host = Host();
        using var alice = ClientFor(host, "alice");
        using var bob = ClientFor(host, "bob");

        var comparison = await CreateAsync(alice, "/api/v1/comparisons", CompareBody);
        var simulation = await CreateAsync(alice, "/api/v1/simulations", PpoBody);

        Assert.Equal(HttpStatusCode.OK, (await alice.GetAsync($"/api/v1/comparisons/{comparison}")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await alice.GetAsync($"/api/v1/simulations/{simulation}")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await alice.GetAsync($"/api/v1/recommendations/{simulation}")).StatusCode);

        await (await bob.GetAsync($"/api/v1/comparisons/{comparison}")).ReadProblemAsync(HttpStatusCode.NotFound, "not_found");
        await (await bob.GetAsync($"/api/v1/simulations/{simulation}")).ReadProblemAsync(HttpStatusCode.NotFound, "not_found");
        await (await bob.GetAsync($"/api/v1/recommendations/{simulation}")).ReadProblemAsync(HttpStatusCode.NotFound, "recommendation_not_found");

        await using var context = db.CreateContext();
        Assert.Equal("test:alice", (await context.ExperimentRuns.SingleAsync(run => run.Id == comparison)).OwnerId);
    }

    [PostgresFact]
    public async Task Recent_runs_list_only_the_callers_own_runs()
    {
        var host = Host();
        var carol = $"carol-{Guid.NewGuid():N}";
        var dave = $"dave-{Guid.NewGuid():N}";
        using var carolClient = ClientFor(host, carol);
        using var daveClient = ClientFor(host, dave);

        var carolsRun = await CreateAsync(carolClient, "/api/v1/comparisons", CompareBody);
        var davesRun = await CreateAsync(daveClient, "/api/v1/simulations", PpoBody);

        var carolList = await RecentAsync(carolClient);
        var daveList = await RecentAsync(daveClient);
        Assert.Equal(1, carolList.GetProperty("totalCount").GetInt32());
        Assert.Equal(carolsRun, carolList.GetProperty("items")[0].GetProperty("id").GetGuid());
        Assert.Equal(1, daveList.GetProperty("totalCount").GetInt32());
        Assert.Equal(davesRun, daveList.GetProperty("items")[0].GetProperty("id").GetGuid());
    }

    [PostgresFact]
    public async Task A_user_with_no_runs_sees_an_empty_history_not_other_peoples()
    {
        var host = Host();
        using var creator = ClientFor(host, "history-creator");
        await CreateAsync(creator, "/api/v1/comparisons", CompareBody);
        using var newcomer = ClientFor(host, $"newcomer-{Guid.NewGuid():N}");

        var list = await RecentAsync(newcomer);

        Assert.Equal(0, list.GetProperty("totalCount").GetInt32());
        Assert.Equal(0, list.GetProperty("items").GetArrayLength());
    }

    [PostgresFact]
    public async Task Runs_without_an_owner_belong_to_no_one()
    {
        var host = Host();
        var legacyId = Guid.NewGuid();
        var simulation = (await SampleDtos.Simulation(Amr.Domain.Enums.StrategyKind.Ppo)) with { Id = legacyId };
        await using (var write = db.CreateContext())
        {
            var model = RunEntityMapper.ToEntity(simulation.Provenance, DateTimeOffset.UtcNow);
            if (!await write.ModelVersions.AnyAsync(existing => existing.Fingerprint == model.Fingerprint))
            {
                write.ModelVersions.Add(model);
                await write.SaveChangesAsync();
            }

            var modelId = await write.ModelVersions.Where(existing => existing.Fingerprint == model.Fingerprint).Select(existing => existing.Id).SingleAsync();
            write.ExperimentRuns.Add(RunEntityMapper.ToEntity(simulation, modelId, DateTimeOffset.UtcNow, ownerId: string.Empty));
            await write.SaveChangesAsync();
        }

        using var anyone = ClientFor(host, "anyone");

        await (await anyone.GetAsync($"/api/v1/simulations/{legacyId}")).ReadProblemAsync(HttpStatusCode.NotFound, "not_found");
        var list = await RecentAsync(anyone);
        Assert.DoesNotContain(list.GetProperty("items").EnumerateArray(), item => item.GetProperty("id").GetGuid() == legacyId);
    }

    [PostgresFact]
    public async Task An_anonymous_caller_cannot_create_or_read_runs()
    {
        var host = Host();
        using var anonymous = AmrApiFactory.CreateBrowserClient(host);

        await (await anonymous.GetAsync("/api/v1/simulations/recent")).ReadProblemAsync(HttpStatusCode.Unauthorized, "authentication_required");
        await (await anonymous.PostJsonAsync("/api/v1/comparisons", CompareBody)).ReadProblemAsync(HttpStatusCode.Unauthorized, "authentication_required");
    }
}
