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
        IReadOnlyDictionary<string, string?>? settings = null)
    {
        var python = new StubHandler(respond ?? Route);
        var client = factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureAppConfiguration((_, configuration) => configuration.AddInMemoryCollection(settings ?? new Dictionary<string, string?>()));
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
            "internal/simulate" => PythonFixtures.Fixture(terminal ? "simulate_200_terminal" : body.Contains("\"strategy\":\"ppo\"", StringComparison.Ordinal) ? "simulate_200_ppo" : "simulate_200_baseline"),
            "internal/compare" => PythonFixtures.Fixture("compare_200"),
            _ => new HttpResponseMessage(HttpStatusCode.NotFound),
        };
    }
}
