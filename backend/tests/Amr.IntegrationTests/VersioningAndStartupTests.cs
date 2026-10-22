using System.Net;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Options;

namespace Amr.IntegrationTests;

public class VersioningAndStartupTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    [Fact]
    public async Task Version_1_routes_respond_and_report_the_supported_versions()
    {
        var response = await factory.CreateClient().GetAsync(HttpTestExtensions.Probe("ok"));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains("1.0", response.Headers.GetValues("api-supported-versions").Single());
    }

    [Fact]
    public async Task An_unsupported_version_is_a_404_problem_with_a_correlation_id()
    {
        var response = await factory.CreateClient().GetAsync("/api/v2/pipeline-probe/ok");

        await response.ReadProblemAsync(HttpStatusCode.NotFound, "not_found");
    }

    [Fact]
    public async Task An_unversioned_route_is_not_served()
    {
        var response = await factory.CreateClient().GetAsync("/api/pipeline-probe/ok");

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    [Theory]
    [InlineData("")]
    [InlineData("not a url")]
    [InlineData("ftp://python.internal/")]
    public void The_host_refuses_to_start_with_an_invalid_python_service_url(string baseUrl)
    {
        using var broken = factory.WithWebHostBuilder(builder => builder.UseSetting("PythonService:BaseUrl", baseUrl));

        var failure = Assert.ThrowsAny<Exception>(() => broken.CreateClient());

        Assert.Contains(Chain(failure), exception => exception is OptionsValidationException);
    }

    [Fact]
    public void The_host_starts_with_the_default_configuration()
    {
        using var client = factory.CreateClient();

        Assert.NotNull(client);
    }

    private static IEnumerable<Exception> Chain(Exception exception)
    {
        for (var current = exception; current is not null; current = current.InnerException!)
        {
            yield return current;
        }
    }
}
