using System.Net;
using Amr.Application.Interfaces.Clients;
using Amr.Infrastructure.Python;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Amr.IntegrationTests.Infrastructure;

/// <summary>
/// The full API stack with real controllers, services, mappings and the real <see cref="PythonServiceClient"/>; only the
/// network is replaced by a stub that serves captured Python responses.
/// </summary>
internal static class StubbedPythonHost
{
    public static (HttpClient Client, StubHandler Python) Create(
        AmrApiFactory factory,
        Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>>? respond = null,
        IReadOnlyDictionary<string, string?>? settings = null,
        string? databaseConnectionString = null)
    {
        var python = new StubHandler(respond ?? Route);
        var configured = new Dictionary<string, string?>(settings ?? new Dictionary<string, string?>());
        if (databaseConnectionString is not null)
        {
            configured["ConnectionStrings:Amr"] = databaseConnectionString;
        }

        var client = factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureAppConfiguration((_, configuration) => configuration.AddInMemoryCollection(configured));
            builder.ConfigureTestServices(services =>
                services.AddHttpClient<IPythonServiceClient, PythonServiceClient>().ConfigurePrimaryHttpMessageHandler(() => python));
        }).CreateClient();
        return (client, python);
    }

    public static async Task<HttpResponseMessage> Route(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        var path = request.RequestUri!.AbsolutePath.TrimStart('/');
        var body = request.Content is null ? string.Empty : await request.Content.ReadAsStringAsync(cancellationToken);
        var terminal = body.Contains("[1,1,1,1,1,1,1]", StringComparison.Ordinal);
        return path switch
        {
            "internal/health" => PythonFixtures.Fixture("health_200"),
            "internal/model" => PythonFixtures.Fixture("model_200"),
            "internal/antibiotics" => PythonFixtures.Fixture("antibiotics_200"),
            "internal/profiles/validate" => PythonFixtures.Fixture(terminal ? "validate_200_terminal" : "validate_200_open"),
            "internal/simulate" => Fresh(terminal ? "simulate_200_terminal" : body.Contains("\"strategy\":\"ppo\"", StringComparison.Ordinal) ? "simulate_200_ppo" : "simulate_200_baseline"),
            "internal/compare" => Fresh("compare_200"),
            _ => new HttpResponseMessage(HttpStatusCode.NotFound),
        };
    }

    /// <summary>Python issues a new run id per execution; a fixed fixture id would make every second save a duplicate.</summary>
    private static HttpResponseMessage Fresh(string fixture) =>
        PythonFixtures.Respond(HttpStatusCode.OK, PythonFixtures.Mutate(fixture, node => node["run_id"] = Guid.NewGuid().ToString()));

    /// <summary>Always answers with one fixture, with a fresh run id unless <paramref name="change"/> sets its own. The call number starts at 1.</summary>
    public static Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> Serving(string fixture, Action<System.Text.Json.Nodes.JsonNode, int>? change = null)
    {
        var calls = 0;
        return (_, _) =>
        {
            var call = Interlocked.Increment(ref calls);
            var body = PythonFixtures.Mutate(fixture, node =>
            {
                node["run_id"] = Guid.NewGuid().ToString();
                change?.Invoke(node, call);
            });
            return Task.FromResult(PythonFixtures.Respond(HttpStatusCode.OK, body));
        };
    }
}
