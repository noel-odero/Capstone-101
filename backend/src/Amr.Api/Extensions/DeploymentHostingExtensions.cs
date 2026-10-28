using System.Net;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.HttpOverrides;

namespace Amr.Api.Extensions;

public static class DeploymentHostingExtensions
{
    public static IServiceCollection AddDeploymentHosting(this IServiceCollection services, IConfiguration configuration)
    {
        var proxyAddress = configuration["ReverseProxy:KnownProxy"];
        if (!string.IsNullOrWhiteSpace(proxyAddress))
        {
            if (!IPAddress.TryParse(proxyAddress, out var proxy))
            {
                throw new InvalidOperationException("ReverseProxy:KnownProxy must be the proxy's IP address.");
            }

            services.Configure<ForwardedHeadersOptions>(options =>
            {
                options.ForwardedHeaders = ForwardedHeaders.XForwardedFor | ForwardedHeaders.XForwardedProto;
                options.ForwardLimit = 1;
                options.KnownProxies.Add(proxy);
            });
        }

        var keysPath = configuration["DataProtection:KeysPath"];
        if (!string.IsNullOrWhiteSpace(keysPath))
        {
            services.AddDataProtection()
                .SetApplicationName("StewardLab")
                .PersistKeysToFileSystem(Directory.CreateDirectory(keysPath));
        }

        return services;
    }
}
