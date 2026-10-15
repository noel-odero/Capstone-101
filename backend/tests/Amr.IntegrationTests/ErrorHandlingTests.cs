using System.Net;
using Amr.Application.Errors;
using Amr.IntegrationTests.Infrastructure;
using Microsoft.Extensions.Logging;

namespace Amr.IntegrationTests;

public class ErrorHandlingTests(AmrApiFactory factory) : IClassFixture<AmrApiFactory>
{
    private readonly HttpClient _client = factory.CreateClient();

    public static TheoryData<ErrorCategory, HttpStatusCode> CategoryStatuses => new()
    {
        { ErrorCategory.InvalidRequest, HttpStatusCode.UnprocessableEntity },
        { ErrorCategory.NotFound, HttpStatusCode.NotFound },
        { ErrorCategory.DependencyUnavailable, HttpStatusCode.ServiceUnavailable },
        { ErrorCategory.UpstreamFailure, HttpStatusCode.BadGateway },
        { ErrorCategory.NotImplemented, HttpStatusCode.NotImplemented },
        { ErrorCategory.Internal, HttpStatusCode.InternalServerError },
    };

    [Theory]
    [MemberData(nameof(CategoryStatuses))]
    public async Task An_application_error_becomes_a_problem_with_its_category_status_and_stable_code(ErrorCategory category, HttpStatusCode status)
    {
        var response = await _client.GetAsync(HttpTestExtensions.Probe($"fail/{category}"));

        var problem = await response.ReadProblemAsync(status, "probe_failure");
        Assert.Equal(StageAProbeController.SafeMessage, problem.GetProperty("detail").GetString());
        Assert.False(problem.TryGetProperty("exception", out _));
        Assert.False(problem.TryGetProperty("stackTrace", out _));
    }

    [Fact]
    public async Task An_unexpected_exception_returns_a_safe_500_and_is_logged_with_the_correlation_id()
    {
        var response = await _client.GetAsync(HttpTestExtensions.Probe("crash"));

        var problem = await response.ReadProblemAsync(HttpStatusCode.InternalServerError, ErrorCodes.InternalError);
        var body = problem.GetRawText();
        Assert.DoesNotContain("secret", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("private", body, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("InvalidOperationException", body, StringComparison.Ordinal);
        Assert.DoesNotContain(" at ", body, StringComparison.Ordinal);

        var correlationId = problem.GetProperty("correlationId").GetString();
        var logged = factory.Logs.Entries.Single(entry =>
            entry.Level == LogLevel.Error && entry.Exception?.Message == StageAProbeController.SecretMessage);
        Assert.Equal(correlationId, logged.CorrelationId);
    }

    [Fact]
    public async Task An_unknown_route_returns_a_problem_with_a_correlation_id()
    {
        var response = await _client.GetAsync("/api/v1/does-not-exist");

        await response.ReadProblemAsync(HttpStatusCode.NotFound, ErrorCodes.NotFound);
    }

    [Fact]
    public async Task A_wrong_method_returns_a_problem()
    {
        var response = await _client.PostAsync(HttpTestExtensions.Probe("ok"), content: null);

        await response.ReadProblemAsync(HttpStatusCode.MethodNotAllowed, "method_not_allowed");
    }
}
