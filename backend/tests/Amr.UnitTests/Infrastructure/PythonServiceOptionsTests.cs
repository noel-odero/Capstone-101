using Amr.Infrastructure.DependencyInjection;
using Amr.Infrastructure.Python;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;

namespace Amr.UnitTests.Infrastructure;

public class PythonServiceOptionsTests
{
    private static PythonServiceOptions Resolve(Dictionary<string, string?> settings)
    {
        var configuration = new ConfigurationBuilder().AddInMemoryCollection(settings).Build();
        using var provider = new ServiceCollection().AddInfrastructure(configuration).BuildServiceProvider();
        return provider.GetRequiredService<IOptions<PythonServiceOptions>>().Value;
    }

    private static Dictionary<string, string?> Settings(string? baseUrl = "http://127.0.0.1:8000", string connect = "5", string request = "60", string health = "3") => new()
    {
        [$"{PythonServiceOptions.SectionName}:BaseUrl"] = baseUrl,
        [$"{PythonServiceOptions.SectionName}:ConnectTimeoutSeconds"] = connect,
        [$"{PythonServiceOptions.SectionName}:RequestTimeoutSeconds"] = request,
        [$"{PythonServiceOptions.SectionName}:HealthTimeoutSeconds"] = health,
    };

    [Fact]
    public void Valid_configuration_binds()
    {
        var options = Resolve(Settings("https://python.internal:8443/"));

        Assert.Equal(new Uri("https://python.internal:8443/"), options.BaseUrl);
        Assert.Equal((5, 60, 3), (options.ConnectTimeoutSeconds, options.RequestTimeoutSeconds, options.HealthTimeoutSeconds));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("not a url")]
    [InlineData("ftp://python.internal/")]
    [InlineData("/relative/path")]
    public void A_missing_or_unusable_base_url_is_rejected(string? baseUrl)
    {
        Assert.Throws<OptionsValidationException>(() => Resolve(Settings(baseUrl)));
    }

    [Theory]
    [InlineData("0", "60", "3")]
    [InlineData("5", "0", "3")]
    [InlineData("5", "601", "3")]
    [InlineData("5", "60", "0")]
    [InlineData("61", "60", "3")]
    public void Timeouts_outside_their_ranges_are_rejected(string connect, string request, string health)
    {
        Assert.Throws<OptionsValidationException>(() => Resolve(Settings(connect: connect, request: request, health: health)));
    }
}
