using System.Net;
using Amr.Api.Extensions;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace Amr.IntegrationTests;

public class DeploymentHostingTests
{
    [Theory]
    [InlineData("172.30.72.10", "198.51.100.24", "https|198.51.100.24")]
    [InlineData("172.30.72.10", "203.0.113.9, 198.51.100.24", "https|198.51.100.24")]
    [InlineData("198.51.100.7", "198.51.100.24", "http|198.51.100.7")]
    public async Task Only_the_configured_proxy_can_forward_https_and_the_client_address(string peer, string forwarded, string expected)
    {
        var configuration = Settings(new() { ["ReverseProxy:KnownProxy"] = "172.30.72.10" });
        var builder = WebApplication.CreateBuilder();
        builder.WebHost.UseTestServer();
        builder.Services.AddDeploymentHosting(configuration);
        await using var app = builder.Build();
        app.Use((HttpContext context, RequestDelegate next) =>
        {
            context.Connection.RemoteIpAddress = IPAddress.Parse(peer);
            return next(context);
        });
        app.UseForwardedHeaders();
        app.Run(context => context.Response.WriteAsync($"{context.Request.Scheme}|{context.Connection.RemoteIpAddress}"));
        await app.StartAsync();
        using var client = app.GetTestClient();
        client.DefaultRequestHeaders.Add("X-Forwarded-For", forwarded);
        client.DefaultRequestHeaders.Add("X-Forwarded-Proto", "https");

        Assert.Equal(expected, await client.GetStringAsync("/"));
    }

    [Fact]
    public void An_invalid_proxy_address_fails_configuration()
    {
        var configuration = Settings(new() { ["ReverseProxy:KnownProxy"] = "not-an-ip" });

        Assert.Throws<InvalidOperationException>(() => new ServiceCollection().AddDeploymentHosting(configuration));
    }

    [Fact]
    public void Protected_session_data_remains_readable_after_a_service_restart()
    {
        var directory = Directory.CreateTempSubdirectory("amr-deployment-keys-");
        try
        {
            var configuration = Settings(new() { ["DataProtection:KeysPath"] = directory.FullName });
            string protectedValue;
            using (var first = new ServiceCollection().AddLogging().AddDeploymentHosting(configuration).BuildServiceProvider())
            {
                protectedValue = first.GetRequiredService<IDataProtectionProvider>()
                    .CreateProtector("session-test").Protect("recorded-session");
            }

            using var restarted = new ServiceCollection().AddLogging().AddDeploymentHosting(configuration).BuildServiceProvider();
            var actual = restarted.GetRequiredService<IDataProtectionProvider>()
                .CreateProtector("session-test").Unprotect(protectedValue);

            Assert.Equal("recorded-session", actual);
        }
        finally
        {
            directory.Delete(recursive: true);
        }
    }

    private static IConfiguration Settings(Dictionary<string, string?> settings) =>
        new ConfigurationBuilder().AddInMemoryCollection(settings).Build();
}
