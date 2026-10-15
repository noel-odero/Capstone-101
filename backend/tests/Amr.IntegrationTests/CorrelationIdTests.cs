using System.Net;
using Amr.IntegrationTests.Infrastructure;

namespace Amr.IntegrationTests;

public class CorrelationIdTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private readonly HttpClient _client = factory.CreateClient();

    private async Task<HttpResponseMessage> GetAsync(string path, string? correlationId = null)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, path);
        if (correlationId is not null)
        {
            request.Headers.TryAddWithoutValidation("X-Correlation-ID", correlationId);
        }

        return await _client.SendAsync(request);
    }

    [Fact]
    public async Task A_correlation_id_is_generated_and_exposed_to_the_endpoint_when_none_is_supplied()
    {
        var response = await GetAsync(HttpTestExtensions.Probe("ok"));

        var header = response.Headers.GetValues("X-Correlation-ID").Single();
        Assert.Equal(32, header.Length);
        Assert.Equal(header, (await response.ReadJsonAsync()).GetProperty("correlationId").GetString());
    }

    [Fact]
    public async Task A_well_formed_supplied_id_is_echoed_in_the_header_and_in_problem_responses()
    {
        var response = await GetAsync(HttpTestExtensions.Probe("fail/NotFound"), "client-trace_1.2");

        Assert.Equal("client-trace_1.2", response.Headers.GetValues("X-Correlation-ID").Single());
        var problem = await response.ReadProblemAsync(HttpStatusCode.NotFound, "probe_failure");
        Assert.Equal("client-trace_1.2", problem.GetProperty("correlationId").GetString());
    }

    [Theory]
    [InlineData("has space")]
    [InlineData("semi;colon")]
    [InlineData("<script>")]
    public async Task A_malformed_supplied_id_is_replaced_rather_than_reflected(string supplied)
    {
        var response = await GetAsync(HttpTestExtensions.Probe("ok"), supplied);

        var header = response.Headers.GetValues("X-Correlation-ID").Single();
        Assert.NotEqual(supplied, header);
        Assert.Equal(32, header.Length);
    }

    [Fact]
    public async Task An_over_long_supplied_id_is_replaced()
    {
        var supplied = new string('a', 65);

        var response = await GetAsync(HttpTestExtensions.Probe("ok"), supplied);

        Assert.Equal(32, response.Headers.GetValues("X-Correlation-ID").Single().Length);
    }

    [Fact]
    public async Task Each_request_without_an_id_gets_a_distinct_one()
    {
        var first = (await GetAsync(HttpTestExtensions.Probe("ok"))).Headers.GetValues("X-Correlation-ID").Single();
        var second = (await GetAsync(HttpTestExtensions.Probe("ok"))).Headers.GetValues("X-Correlation-ID").Single();

        Assert.NotEqual(first, second);
    }
}
