using Amr.Application.Interfaces.Clients;
using Amr.Infrastructure.Python;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace Amr.Infrastructure.DependencyInjection;

public static class InfrastructureServiceCollectionExtensions
{
    public static IServiceCollection AddInfrastructure(this IServiceCollection services, IConfiguration configuration)
    {
        services.AddOptions<PythonServiceOptions>()
            .Bind(configuration.GetSection(PythonServiceOptions.SectionName))
            .ValidateDataAnnotations()
            .ValidateOnStart();

        services.AddSingleton<PythonServiceErrorMapper>();
        services.AddHttpClient<IPythonServiceClient, PythonServiceClient>(ConfigurePythonClient)
            .ConfigurePrimaryHttpMessageHandler(CreatePythonHandler);
        services.AddTransient<IDependencyHealthProbe, PythonServiceHealthChecker>();

        return services;
    }

    private static void ConfigurePythonClient(IServiceProvider provider, HttpClient client)
    {
        var options = provider.GetRequiredService<IOptions<PythonServiceOptions>>().Value;
        client.BaseAddress = new Uri(options.BaseUrl!.AbsoluteUri.TrimEnd('/') + "/");
        client.Timeout = Timeout.InfiniteTimeSpan; // per-call timeouts are applied by PythonServiceClient
        client.DefaultRequestHeaders.Accept.ParseAdd("application/json");
    }

    private static SocketsHttpHandler CreatePythonHandler(IServiceProvider provider) => new()
    {
        ConnectTimeout = TimeSpan.FromSeconds(provider.GetRequiredService<IOptions<PythonServiceOptions>>().Value.ConnectTimeoutSeconds),
        PooledConnectionLifetime = TimeSpan.FromMinutes(2),
        AllowAutoRedirect = false,
    };
}
