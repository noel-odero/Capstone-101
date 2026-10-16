using Amr.Application.DTOs.Health;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Amr.IntegrationTests;

public class PythonIntegrationWiringTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    // A refused connection and a dropped one (firewall) differ by OS; both mean the service cannot be reached.
    private static readonly string[] UnreachableCodes = [ErrorCodes.PythonServiceUnavailable, ErrorCodes.PythonServiceTimeout];

    [Fact]
    public void The_python_client_and_both_health_probes_are_registered_in_the_host()
    {
        using var scope = factory.Services.CreateScope();

        Assert.NotNull(factory.Services.GetRequiredService<IPythonServiceClient>());
        var probes = scope.ServiceProvider.GetServices<IDependencyHealthProbe>().Select(probe => probe.GetType()).ToList();
        Assert.Contains(typeof(Amr.Infrastructure.Python.PythonServiceHealthChecker), probes);
        Assert.Contains(typeof(Amr.Infrastructure.Persistence.DatabaseHealthProbe), probes);
    }

    [Fact]
    public void A_connection_string_supplied_by_a_test_overrides_the_harness_default_but_a_host_setting_does_not()
    {
        using var overridden = factory.WithWebHostBuilder(builder => builder.ConfigureAppConfiguration((_, configuration) =>
            configuration.AddInMemoryCollection(new Dictionary<string, string?> { ["ConnectionStrings:Amr"] = "Host=override.test;Database=x" })));
        using var hostSetting = factory.WithWebHostBuilder(builder => builder.UseSetting("ConnectionStrings:Amr", "Host=ignored.test;Database=x"));

        var explicitValue = overridden.Services.GetRequiredService<Microsoft.Extensions.Options.IOptions<Amr.Infrastructure.Persistence.DatabaseOptions>>().Value.ConnectionString;
        var hostValue = hostSetting.Services.GetRequiredService<Microsoft.Extensions.Options.IOptions<Amr.Infrastructure.Persistence.DatabaseOptions>>().Value.ConnectionString;

        Assert.Equal("Host=override.test;Database=x", explicitValue);
        Assert.Equal(AmrApiFactory.UnreachableDatabase, hostValue);
    }

    [Fact]
    public async Task With_no_python_service_listening_readiness_is_unhealthy_with_stable_codes_and_no_infrastructure_details()
    {
        using var unreachable = factory.WithWebHostBuilder(builder =>
        {
            builder.UseSetting("PythonService:BaseUrl", "http://127.0.0.1:1");
            builder.UseSetting("PythonService:ConnectTimeoutSeconds", "2");
        });
        using var scope = unreachable.Services.CreateScope();
        var probe = scope.ServiceProvider.GetServices<IDependencyHealthProbe>().OfType<Amr.Infrastructure.Python.PythonServiceHealthChecker>().Single();

        var components = await probe.CheckAsync(CancellationToken.None);

        var service = components.Single(component => component.Name == HealthComponents.PythonService);
        Assert.Equal(HealthState.Unhealthy, service.Status);
        Assert.Contains(service.Detail, UnreachableCodes);
        Assert.Equal(new ComponentHealthDto(HealthComponents.Model, HealthState.Unhealthy, ErrorCodes.ModelUnavailable), components.Single(component => component.Name == HealthComponents.Model));
    }

    [Fact]
    public async Task With_no_python_service_listening_an_operation_is_a_503_application_error_not_a_raw_connection_exception()
    {
        using var unreachable = factory.WithWebHostBuilder(builder =>
        {
            builder.UseSetting("PythonService:BaseUrl", "http://127.0.0.1:1");
            builder.UseSetting("PythonService:ConnectTimeoutSeconds", "2");
        });
        var client = unreachable.Services.GetRequiredService<IPythonServiceClient>();

        var error = await Assert.ThrowsAsync<AmrException>(() => client.GetModelAsync(CancellationToken.None));

        Assert.Equal(ErrorCategory.DependencyUnavailable, error.Category);
        Assert.Contains(error.Code, UnreachableCodes);
    }
}
