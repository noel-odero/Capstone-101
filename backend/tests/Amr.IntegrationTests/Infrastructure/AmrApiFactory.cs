using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Amr.IntegrationTests.Infrastructure;

public sealed class AmrApiFactory : WebApplicationFactory<Program>
{
    public const string UnreachableDatabase = "Host=127.0.0.1;Port=1;Database=amr;Username=amr;Password=unused;Timeout=2;Command Timeout=2";

    public CapturingLoggerProvider Logs { get; } = new();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        // Tests that never reach the database get a closed port; tests that do pass their own connection string.
        builder.ConfigureAppConfiguration((_, configuration) =>
            configuration.AddInMemoryCollection(new Dictionary<string, string?> { ["ConnectionStrings:Amr"] = UnreachableDatabase }));
        builder.ConfigureLogging(logging => logging.AddProvider(Logs));
        builder.ConfigureTestServices(services =>
            services.AddControllers().AddApplicationPart(typeof(StageAProbeController).Assembly));
    }
}
