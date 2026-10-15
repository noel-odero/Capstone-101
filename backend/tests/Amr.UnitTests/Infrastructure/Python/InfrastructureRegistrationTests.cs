using System.Net;
using Amr.Application.Interfaces.Clients;
using Amr.Infrastructure.DependencyInjection;
using Amr.Infrastructure.Python;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Amr.UnitTests.Infrastructure.Python;

public class InfrastructureRegistrationTests
{
    private static ServiceProvider Build(string baseUrl, StubHandler handler)
    {
        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?> { ["PythonService:BaseUrl"] = baseUrl })
            .Build();
        var services = new ServiceCollection().AddLogging().AddInfrastructure(configuration);
        services.AddHttpClient<IPythonServiceClient, PythonServiceClient>().ConfigurePrimaryHttpMessageHandler(() => handler);
        return services.BuildServiceProvider();
    }

    [Theory]
    [InlineData("http://python.internal:8000", "http://python.internal:8000/internal/health")]
    [InlineData("http://python.internal:8000/", "http://python.internal:8000/internal/health")]
    [InlineData("http://python.internal:8000/svc", "http://python.internal:8000/svc/internal/health")]
    [InlineData("https://python.internal/svc/", "https://python.internal/svc/internal/health")]
    public async Task The_configured_base_url_is_used_and_a_path_base_is_preserved(string baseUrl, string expected)
    {
        var handler = StubHandler.Returning(() => PythonFixtures.Fixture("health_200"));
        await using var provider = Build(baseUrl, handler);

        await provider.GetRequiredService<IPythonServiceClient>().GetHealthAsync(CancellationToken.None);

        var request = handler.Requests.Single();
        Assert.Equal(new Uri(expected), request.Uri);
        Assert.Contains("application/json", request.Accept, StringComparison.Ordinal);
    }

    [Fact]
    public void The_client_and_the_health_probe_resolve_from_the_container()
    {
        using var provider = Build("http://python.internal:8000", StubHandler.Returning(() => new HttpResponseMessage(HttpStatusCode.OK)));

        Assert.IsType<PythonServiceClient>(provider.GetRequiredService<IPythonServiceClient>());
        Assert.IsType<PythonServiceHealthChecker>(provider.GetRequiredService<IDependencyHealthProbe>());
        Assert.NotNull(provider.GetRequiredService<PythonServiceErrorMapper>());
    }

    [Fact]
    public void The_configured_http_client_leaves_timeouts_to_the_python_client()
    {
        using var provider = Build("http://python.internal:8000", StubHandler.Returning(() => new HttpResponseMessage(HttpStatusCode.OK)));

        var httpClient = provider.GetRequiredService<IHttpClientFactory>().CreateClient(nameof(IPythonServiceClient));

        Assert.Equal(Timeout.InfiniteTimeSpan, httpClient.Timeout);
        Assert.Equal(new Uri("http://python.internal:8000/"), httpClient.BaseAddress);
    }

    [Fact]
    public void No_retry_or_resilience_package_is_referenced_by_infrastructure()
    {
        var project = File.ReadAllText(Path.Combine(BackendRoot(), "src", "Amr.Infrastructure", "Amr.Infrastructure.csproj"));

        Assert.DoesNotContain("Resilience", project, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("Polly", project, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void The_infrastructure_sources_register_no_retry_handlers()
    {
        var sources = Directory.EnumerateFiles(Path.Combine(BackendRoot(), "src", "Amr.Infrastructure"), "*.cs", SearchOption.AllDirectories)
            .Select(File.ReadAllText)
            .ToList();

        Assert.DoesNotContain(sources, text => text.Contains("AddResilienceHandler", StringComparison.Ordinal)
            || text.Contains("AddStandardResilienceHandler", StringComparison.Ordinal)
            || text.Contains("AddPolicyHandler", StringComparison.Ordinal));
    }

    private static string BackendRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Amr.sln")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? throw new InvalidOperationException("Amr.sln not found.");
    }
}
