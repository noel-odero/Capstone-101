using System.Net;
using Amr.Application.Errors;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace Amr.IntegrationTests.FullStack;

/// <summary>What the API says and does when Python succeeded but the database is down. None of these need a PostgreSQL server.</summary>
public class DatabaseUnavailableTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private const string PpoBody = """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"ppo","environmentSeed":100001}""";

    [Fact]
    public async Task A_run_that_cannot_be_saved_is_a_503_that_says_no_record_exists_and_returns_no_result()
    {
        var runId = Guid.NewGuid();
        var (client, python) = StubbedPythonHost.Create(factory, StubbedPythonHost.Serving("simulate_200_ppo", (node, _) => node["run_id"] = runId.ToString()));

        var response = await client.PostJsonAsync("/api/v1/simulations", PpoBody);

        var problem = await response.ReadProblemAsync(HttpStatusCode.ServiceUnavailable, ErrorCodes.DatabaseUnavailable);
        Assert.Contains("No record exists", problem.GetProperty("detail").GetString(), StringComparison.Ordinal);
        Assert.False(problem.TryGetProperty("id", out _));
        Assert.False(problem.TryGetProperty("isPersisted", out _));
        Assert.False(problem.TryGetProperty("result", out _));
        Assert.DoesNotContain(runId.ToString(), problem.GetRawText(), StringComparison.Ordinal);
        Assert.Equal(1, python.CallCount);
    }

    [Fact]
    public async Task The_failure_is_logged_with_the_run_id_and_the_responses_correlation_id_and_no_secrets()
    {
        var runId = Guid.NewGuid();
        var (client, _) = StubbedPythonHost.Create(factory, StubbedPythonHost.Serving("simulate_200_ppo", (node, _) => node["run_id"] = runId.ToString()));
        using var request = new HttpRequestMessage(HttpMethod.Post, "/api/v1/simulations")
        {
            Content = new StringContent(PpoBody, System.Text.Encoding.UTF8, "application/json"),
        };
        request.Headers.Add("X-Correlation-ID", "stage-d-correlation-1");

        var response = await client.SendAsync(request);

        var problem = await response.ReadProblemAsync(HttpStatusCode.ServiceUnavailable, ErrorCodes.DatabaseUnavailable);
        Assert.Equal("stage-d-correlation-1", problem.GetProperty("correlationId").GetString());
        var entry = Assert.Single(factory.Logs.Entries, log => log.Level == LogLevel.Error && log.Message.Contains(runId.ToString(), StringComparison.Ordinal));
        Assert.Equal("stage-d-correlation-1", entry.CorrelationId);
        Assert.Contains("no public record", entry.Message, StringComparison.Ordinal);
        Assert.DoesNotContain("unused", entry.Message, StringComparison.Ordinal);
        Assert.DoesNotContain("Password", entry.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task A_comparison_that_cannot_be_saved_is_also_a_503_and_python_is_not_called_again()
    {
        var (client, python) = StubbedPythonHost.Create(factory);

        var response = await client.PostJsonAsync("/api/v1/comparisons", """{"resistanceProfile":[0,1,0,0,0,0,0],"environmentSeed":100001,"policySeed":900001}""");

        await response.ReadProblemAsync(HttpStatusCode.ServiceUnavailable, ErrorCodes.DatabaseUnavailable);
        Assert.Equal(1, python.CallCount);
    }

    [Theory]
    [InlineData("/api/v1/simulations/3f2504e0-4f89-41d3-9a0c-0305e82c3301")]
    [InlineData("/api/v1/comparisons/3f2504e0-4f89-41d3-9a0c-0305e82c3301")]
    [InlineData("/api/v1/recommendations/3f2504e0-4f89-41d3-9a0c-0305e82c3301")]
    [InlineData("/api/v1/simulations/recent")]
    public async Task Reading_while_the_database_is_down_is_a_503_not_a_404_or_an_empty_list(string url)
    {
        var (client, python) = StubbedPythonHost.Create(factory);

        var response = await client.GetAsync(url);

        var problem = await response.ReadProblemAsync(HttpStatusCode.ServiceUnavailable, ErrorCodes.DatabaseUnavailable);
        Assert.DoesNotContain("127.0.0.1", problem.GetRawText(), StringComparison.Ordinal);
        Assert.Equal(0, python.CallCount);
    }

    [Fact]
    public async Task Readiness_reports_the_database_with_a_stable_code_and_leaks_no_connection_details()
    {
        var (client, _) = StubbedPythonHost.Create(factory);

        var response = await client.GetAsync("/api/v1/health");

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        var text = await response.Content.ReadAsStringAsync();
        var components = System.Text.Json.JsonDocument.Parse(text).RootElement.GetProperty("components").EnumerateArray()
            .ToDictionary(item => item.GetProperty("name").GetString()!, item => (item.GetProperty("status").GetString(), item.GetProperty("detail").GetString()));
        Assert.Equal(("healthy", null), components["pythonService"]);
        Assert.Equal(("unhealthy", "database_unavailable"), components["database"]);
        Assert.DoesNotContain("127.0.0.1", text, StringComparison.Ordinal);
        Assert.DoesNotContain("Password", text, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Liveness_does_not_depend_on_the_database()
    {
        var (client, _) = StubbedPythonHost.Create(factory);

        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync("/api/v1/health/live")).StatusCode);
    }
}

/// <summary>A reachable database whose migrations were never applied: saving fails safely and readiness says why.</summary>
public class UnmigratedDatabaseTests(AmrApiFactory factory, UnmigratedPostgresDatabaseFixture db)
    : IClassFixture<AmrApiFactory>, IClassFixture<UnmigratedPostgresDatabaseFixture>
{
    [PostgresFact]
    public async Task Saving_without_a_schema_is_a_500_persistence_failure_not_an_unavailable_database()
    {
        var (client, python) = StubbedPythonHost.Create(factory, databaseConnectionString: db.ConnectionString);

        var response = await client.PostJsonAsync("/api/v1/simulations", """{"resistanceProfile":[0,1,0,0,0,0,0],"strategy":"ppo","environmentSeed":100001}""");

        var problem = await response.ReadProblemAsync(HttpStatusCode.InternalServerError, ErrorCodes.PersistenceFailed);
        Assert.Contains("No record exists", problem.GetProperty("detail").GetString(), StringComparison.Ordinal);
        Assert.Equal(1, python.CallCount);
    }

    [PostgresFact]
    public async Task Readiness_reports_pending_migrations_instead_of_silently_migrating()
    {
        var (client, _) = StubbedPythonHost.Create(factory, databaseConnectionString: db.ConnectionString);

        var response = await client.GetAsync("/api/v1/health");
        var again = await client.GetAsync("/api/v1/health");

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        var database = (await response.ReadJsonAsync()).GetProperty("components").EnumerateArray().Single(item => item.GetProperty("name").GetString() == "database");
        Assert.Equal("database_migrations_pending", database.GetProperty("detail").GetString());
        Assert.Equal(HttpStatusCode.ServiceUnavailable, again.StatusCode);
        await using var context = db.CreateContext();
        Assert.Empty(await context.Database.GetAppliedMigrationsAsync());
    }
}
