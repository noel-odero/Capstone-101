using Amr.Application.Interfaces.Clients;
using Amr.Application.Interfaces.Persistence;
using Amr.Infrastructure.Persistence;
using Amr.Infrastructure.Python;
using Microsoft.EntityFrameworkCore;
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

        AddPersistence(services, configuration);

        return services;
    }

    /// <summary>The connection string is read when options are first used, so host configuration added after registration is honored.</summary>
    private static void AddPersistence(IServiceCollection services, IConfiguration configuration)
    {
        services.AddOptions<DatabaseOptions>()
            .Bind(configuration.GetSection(DatabaseOptions.SectionName))
            .Configure(options => options.ConnectionString = configuration.GetConnectionString(DatabaseOptions.ConnectionStringName))
            .ValidateDataAnnotations()
            .ValidateOnStart();

        services.AddDbContext<AmrDbContext>((provider, builder) =>
        {
            var database = provider.GetRequiredService<IOptions<DatabaseOptions>>().Value;
            builder
                .UseNpgsql(database.ConnectionString, npgsql => npgsql.CommandTimeout(database.CommandTimeoutSeconds))
                .UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking);
        });

        services.AddSingleton(TimeProvider.System);
        services.AddScoped<IRunRepository, RunRepository>();
        services.AddScoped<IDependencyHealthProbe, DatabaseHealthProbe>();
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
