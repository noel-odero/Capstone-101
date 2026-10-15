using System.Net;
using Amr.Application.Errors;
using Amr.IntegrationTests.Infrastructure;

namespace Amr.IntegrationTests;

public class RequestValidationTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private readonly HttpClient _client = factory.CreateClient();

    private static string Profile(string values) => $$"""{"resistanceProfile": {{values}}}""";

    private static string Simulation(string extra) => $$"""{"resistanceProfile": [0,1,0,0,0,0,0], {{extra}}}""";

    [Theory]
    [InlineData("[0,0,0,0,0,0]")]
    [InlineData("[0,0,0,0,0,0,0,0]")]
    [InlineData("[0,0,0,0,0,0,2]")]
    [InlineData("[-1,0,0,0,0,0,0]")]
    [InlineData("[]")]
    [InlineData("null")]
    public async Task A_malformed_profile_is_rejected_with_422_and_a_field_error(string values)
    {
        var response = await _client.PostJsonAsync(HttpTestExtensions.Probe("profile"), Profile(values));

        var problem = await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
        Assert.True(problem.GetProperty("errors").TryGetProperty("resistanceProfile", out var messages));
        Assert.NotEmpty(messages.EnumerateArray());
    }

    [Theory]
    [InlineData("""["0",0,0,0,0,0,0]""")]
    [InlineData("[0.5,0,0,0,0,0,0]")]
    [InlineData("[true,0,0,0,0,0,0]")]
    [InlineData("\"0000000\"")]
    public async Task Wrongly_typed_profile_values_are_rejected_without_echoing_framework_internals(string values)
    {
        var response = await _client.PostJsonAsync(HttpTestExtensions.Probe("profile"), Profile(values));

        var problem = await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
        Assert.DoesNotContain("System.", problem.GetRawText(), StringComparison.Ordinal);
        Assert.DoesNotContain("LineNumber", problem.GetRawText(), StringComparison.Ordinal);
    }

    [Fact]
    public async Task A_missing_profile_and_malformed_json_are_422()
    {
        var missing = await _client.PostJsonAsync(HttpTestExtensions.Probe("profile"), "{}");
        var malformed = await _client.PostJsonAsync(HttpTestExtensions.Probe("profile"), "{not json");

        await missing.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
        await malformed.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
    }

    [Fact]
    public async Task An_empty_body_is_422_like_every_other_unusable_input()
    {
        var response = await _client.PostAsync(HttpTestExtensions.Probe("profile"), new StringContent(string.Empty, System.Text.Encoding.UTF8, "application/json"));

        await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
    }

    [Theory]
    [InlineData("page=abc", "page")]
    [InlineData("pageSize=1.5", "pageSize")]
    public async Task Unparseable_query_values_are_422_with_a_field_error(string query, string field)
    {
        var response = await _client.GetAsync(HttpTestExtensions.Probe($"recent?{query}"));

        var problem = await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
        Assert.True(problem.GetProperty("errors").TryGetProperty(field, out _));
    }

    [Fact]
    public async Task An_unsupported_content_type_is_the_one_documented_4xx_that_is_not_422()
    {
        var response = await _client.PostAsync(HttpTestExtensions.Probe("profile"), new StringContent("{}", System.Text.Encoding.UTF8, "text/plain"));

        await response.ReadProblemAsync(HttpStatusCode.UnsupportedMediaType, "unsupported_media_type");
    }

    [Fact]
    public async Task A_valid_profile_is_accepted()
    {
        var response = await _client.PostJsonAsync(HttpTestExtensions.Probe("profile"), Profile("[1,1,1,1,1,1,1]"));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Theory]
    [InlineData("ppo")]
    [InlineData("random_susceptible_baseline")]
    public async Task Allowed_strategy_identifiers_are_accepted_and_echoed_unchanged(string strategy)
    {
        var response = await _client.PostJsonAsync(HttpTestExtensions.Probe("simulation"), Simulation($"\"strategy\": \"{strategy}\""));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(strategy, (await response.ReadJsonAsync()).GetProperty("strategy").GetString());
    }

    [Theory]
    [InlineData("\"strategy\": \"greedy\"")]
    [InlineData("\"strategy\": \"PPO2\"")]
    [InlineData("\"strategy\": 1")]
    [InlineData("\"strategy\": null")]
    [InlineData("\"environmentSeed\": 1")]
    public async Task A_missing_or_unknown_strategy_is_rejected(string extra)
    {
        var response = await _client.PostJsonAsync(HttpTestExtensions.Probe("simulation"), Simulation(extra));

        await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
    }

    [Theory]
    [InlineData("environmentSeed", "-1")]
    [InlineData("environmentSeed", "4294967296")]
    [InlineData("policySeed", "-5")]
    [InlineData("policySeed", "4294967296")]
    public async Task Seeds_outside_the_python_range_are_rejected(string field, string value)
    {
        var response = await _client.PostJsonAsync(HttpTestExtensions.Probe("simulation"), Simulation($"\"strategy\": \"ppo\", \"{field}\": {value}"));

        var problem = await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
        Assert.True(problem.GetProperty("errors").TryGetProperty(field, out _));
    }

    [Theory]
    [InlineData("0")]
    [InlineData("4294967295")]
    public async Task Boundary_seeds_are_accepted(string value)
    {
        var response = await _client.PostJsonAsync(HttpTestExtensions.Probe("simulation"), Simulation($"\"strategy\": \"ppo\", \"environmentSeed\": {value}, \"policySeed\": {value}"));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Theory]
    [InlineData("horizon", "3")]
    [InlineData("scenarioId", "\"SENSITIVITY_Q_050\"")]
    public async Task Horizon_and_scenario_are_fixed_by_the_model_and_cannot_be_supplied(string field, string value)
    {
        var response = await _client.PostJsonAsync(HttpTestExtensions.Probe("simulation"), Simulation($"\"strategy\": \"ppo\", \"{field}\": {value}"));

        await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
    }

    [Fact]
    public async Task The_recent_runs_query_defaults_to_the_first_page_with_the_default_size()
    {
        var body = await (await _client.GetAsync(HttpTestExtensions.Probe("recent"))).ReadJsonAsync();

        Assert.Equal(1, body.GetProperty("page").GetInt32());
        Assert.Equal(20, body.GetProperty("pageSize").GetInt32());
    }

    [Theory]
    [InlineData("page=0", "page")]
    [InlineData("page=-1", "page")]
    [InlineData("pageSize=0", "pageSize")]
    [InlineData("pageSize=51", "pageSize")]
    public async Task The_recent_runs_query_rejects_non_positive_pages_and_oversized_page_sizes(string query, string field)
    {
        var response = await _client.GetAsync(HttpTestExtensions.Probe($"recent?{query}"));

        var problem = await response.ReadProblemAsync(HttpStatusCode.UnprocessableEntity, ErrorCodes.ValidationFailed);
        Assert.True(problem.GetProperty("errors").TryGetProperty(field, out _));
    }

    [Fact]
    public async Task The_maximum_page_size_is_accepted()
    {
        var response = await _client.GetAsync(HttpTestExtensions.Probe("recent?pageSize=50"));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }
}
