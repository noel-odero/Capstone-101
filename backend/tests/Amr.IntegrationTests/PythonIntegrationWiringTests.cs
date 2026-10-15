using Amr.Application.DTOs.Health;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Clients;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.Extensions.DependencyInjection;

namespace Amr.IntegrationTests;

public class PythonIntegrationWiringTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    // A refused connection and a dropped one (firewall) differ by OS; both mean the service cannot be reached.
    private static readonly string[] UnreachableCodes = [ErrorCodes.PythonServiceUnavailable, ErrorCodes.PythonServiceTimeout];

    [Fact]
    public void The_python_client_and_health_probe_are_registered_in_the_host()
    {
        Assert.NotNull(factory.Services.GetRequiredService<IPythonServiceClient>());
        Assert.NotEmpty(factory.Services.GetServices<IDependencyHealthProbe>());
    }

    [Fact]
    public async Task With_no_python_service_listening_readiness_is_unhealthy_with_stable_codes_and_no_infrastructure_details()
    {
        using var unreachable = factory.WithWebHostBuilder(builder =>
        {
            builder.UseSetting("PythonService:BaseUrl", "http://127.0.0.1:1");
            builder.UseSetting("PythonService:ConnectTimeoutSeconds", "2");
        });
        var probe = unreachable.Services.GetRequiredService<IDependencyHealthProbe>();

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
