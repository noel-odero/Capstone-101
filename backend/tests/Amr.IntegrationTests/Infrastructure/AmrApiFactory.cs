using Amr.Api.Authentication;
using Microsoft.AspNetCore.Antiforgery;
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
    public const string DefaultUser = "researcher-a";

    public CapturingLoggerProvider Logs { get; } = new();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        // Tests that never reach the database get a closed port; tests that do pass their own connection string.
        builder.ConfigureAppConfiguration((_, configuration) =>
            configuration.AddInMemoryCollection(new Dictionary<string, string?> { ["ConnectionStrings:Amr"] = UnreachableDatabase }));
        builder.ConfigureLogging(logging => logging.AddProvider(Logs));
        builder.ConfigureTestServices(services =>
        {
            services.AddControllers().AddApplicationPart(typeof(StageAProbeController).Assembly);

            // A request with X-Test-User is authenticated as that test user; otherwise the real cookie session applies.
            services.AddAuthentication(options => options.DefaultAuthenticateScheme = TestAuthHandler.PolicyScheme)
                .AddScheme<Microsoft.AspNetCore.Authentication.AuthenticationSchemeOptions, TestAuthHandler>(TestAuthHandler.SchemeName, _ => { })
                .AddPolicyScheme(TestAuthHandler.PolicyScheme, displayName: null, policy =>
                    policy.ForwardDefaultSelector = context =>
                        context.Request.Headers.ContainsKey(TestAuthHandler.UserHeader) ? TestAuthHandler.SchemeName : AmrAuthentication.CookieScheme);

            var antiforgery = services.Single(descriptor => descriptor.ServiceType == typeof(IAntiforgery));
            services.Remove(antiforgery);
            services.AddSingleton<IAntiforgery>(provider =>
                new BypassableAntiforgery((IAntiforgery)ActivatorUtilities.CreateInstance(provider, antiforgery.ImplementationType!)));
        });
    }

    /// <summary>Ordinary tests act as a signed-in test user whose requests skip CSRF validation; the dedicated tests below do not.</summary>
    protected override void ConfigureClient(HttpClient client)
    {
        base.ConfigureClient(client);
        client.DefaultRequestHeaders.Add(TestAuthHandler.UserHeader, DefaultUser);
        client.DefaultRequestHeaders.Add(TestAuthHandler.BypassCsrfHeader, "1");
    }

    /// <summary>A client with no identity and the real CSRF check: it can only use what a browser could.</summary>
    public HttpClient CreateBrowserClient(HandleCookies handleCookies = HandleCookies.Yes) => CreateBrowserClient(this, handleCookies);

    internal static HttpClient CreateBrowserClient(WebApplicationFactory<Program> factory, HandleCookies handleCookies = HandleCookies.Yes)
    {
        var client = factory.CreateClient(new WebApplicationFactoryClientOptions { AllowAutoRedirect = false, HandleCookies = handleCookies == HandleCookies.Yes });
        client.DefaultRequestHeaders.Remove(TestAuthHandler.UserHeader);
        client.DefaultRequestHeaders.Remove(TestAuthHandler.BypassCsrfHeader);
        return client;
    }

    /// <summary>A client for another test user, with the CSRF check skipped like the default client.</summary>
    public HttpClient CreateClientFor(string user)
    {
        var client = CreateClient();
        client.DefaultRequestHeaders.Remove(TestAuthHandler.UserHeader);
        client.DefaultRequestHeaders.Add(TestAuthHandler.UserHeader, user);
        return client;
    }
}

public enum HandleCookies
{
    Yes,
    No,
}
