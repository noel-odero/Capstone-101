using System.Net;
using System.Net.Sockets;
using Amr.Application.Errors;
using Amr.Application.PythonContracts;

namespace Amr.UnitTests.Infrastructure.Python;

public class PythonServiceClientFailureTests
{
    private static readonly PythonSimulateRequest SimulateRequest = new([0, 1, 0, 0, 0, 0, 0], PythonStrategyIds.Ppo, 1, null);
    private static readonly PythonCompareRequest CompareRequest = new([0, 1, 0, 0, 0, 0, 0], 1, 1);

    private static void AssertError(AmrException error, ErrorCategory category, string code) =>
        Assert.Equal((category, code), (error.Category, error.Code));

    public static TheoryData<string> MalformedBodies => new()
    {
        { "" },
        { "not json" },
        { "<html><body>Bad gateway</body></html>" },
        { "[]" },
        { "null" },
        { "{}" },
        { """{"detail": "Not Found"}""" },
        { PythonFixtures.Mutate("model_200", node => node.AsObject().Remove("model_id")) },
        { PythonFixtures.Mutate("model_200", node => node["model_id"] = null) },
        { PythonFixtures.Mutate("model_200", node => node["horizon"] = "eight") },
        { PythonFixtures.Mutate("model_200", node => node["horizon"] = 8.5) },
        { PythonFixtures.Mutate("model_200", node => node["observation"] = null) },
        { PythonFixtures.Mutate("model_200", node => node["antibiotic_order"] = "CIPROFLOXACIN") },
    };

    [Theory]
    [MemberData(nameof(MalformedBodies))]
    public async Task A_malformed_success_body_is_an_invalid_response_not_a_partial_result(string body)
    {
        var client = ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.OK, body)));

        var error = await Assert.ThrowsAsync<AmrException>(() => client.GetModelAsync(CancellationToken.None));

        AssertError(error, ErrorCategory.UpstreamFailure, ErrorCodes.PythonServiceInvalidResponse);
    }

    [Fact]
    public async Task A_run_missing_a_required_trace_member_is_rejected()
    {
        var body = PythonFixtures.Mutate("simulate_200_ppo", node => node["result"]!["steps"]![0]!.AsObject().Remove("transition_status"));
        var client = ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.OK, body)));

        var error = await Assert.ThrowsAsync<AmrException>(() => client.SimulateAsync(SimulateRequest, CancellationToken.None));

        AssertError(error, ErrorCategory.UpstreamFailure, ErrorCodes.PythonServiceInvalidResponse);
    }

    [Fact]
    public async Task Non_json_content_with_a_success_status_is_an_invalid_response()
    {
        var client = ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.OK, "OK", "text/plain")));

        var error = await Assert.ThrowsAsync<AmrException>(() => client.GetAntibioticsAsync(CancellationToken.None));

        AssertError(error, ErrorCategory.UpstreamFailure, ErrorCodes.PythonServiceInvalidResponse);
    }

    public static TheoryData<string, HttpStatusCode, ErrorCategory, string> ErrorEnvelopes => new()
    {
        { "validate_422_invalid_context", HttpStatusCode.UnprocessableEntity, ErrorCategory.InvalidRequest, ErrorCodes.ValidationFailed },
        { "validate_422_request_validation", HttpStatusCode.UnprocessableEntity, ErrorCategory.InvalidRequest, ErrorCodes.ValidationFailed },
        { "model_503_checkpoint_integrity_failure", HttpStatusCode.ServiceUnavailable, ErrorCategory.DependencyUnavailable, ErrorCodes.ModelUnavailable },
        { "compare_500_contract_violation", HttpStatusCode.InternalServerError, ErrorCategory.Internal, ErrorCodes.ComparisonContractViolation },
        { "simulate_500_internal_error", HttpStatusCode.InternalServerError, ErrorCategory.Internal, ErrorCodes.InternalError },
    };

    [Theory]
    [MemberData(nameof(ErrorEnvelopes))]
    public async Task Real_python_error_envelopes_map_to_stable_public_errors(string fixture, HttpStatusCode status, ErrorCategory category, string code)
    {
        var client = ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Fixture(fixture, status)));

        var error = await Assert.ThrowsAsync<AmrException>(() => client.CompareAsync(CompareRequest, CancellationToken.None));

        AssertError(error, category, code);
    }

    [Theory]
    [InlineData("model_not_loaded")]
    [InlineData("checkpoint_integrity_failure")]
    [InlineData("model_contract_mismatch")]
    [InlineData("model_or_data_unavailable")]
    public async Task Every_model_unavailability_code_is_reported_as_model_unavailable(string pythonCode)
    {
        var body = $$$"""{"error":{"code":"{{{pythonCode}}}","message":"m","request_id":"r"}}""";
        var client = ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.ServiceUnavailable, body)));

        var error = await Assert.ThrowsAsync<AmrException>(() => client.GetModelAsync(CancellationToken.None));

        AssertError(error, ErrorCategory.DependencyUnavailable, ErrorCodes.ModelUnavailable);
    }

    [Theory]
    [InlineData(500, "empty_action_mask", ErrorCategory.Internal, ErrorCodes.InternalError)]
    [InlineData(500, "infeasible_policy_action", ErrorCategory.Internal, ErrorCodes.InternalError)]
    [InlineData(500, "inference_failure", ErrorCategory.Internal, ErrorCodes.InternalError)]
    [InlineData(500, "some_future_code", ErrorCategory.Internal, ErrorCodes.InternalError)]
    [InlineData(404, "http_error", ErrorCategory.UpstreamFailure, ErrorCodes.PythonServiceInvalidResponse)]
    [InlineData(409, "some_future_code", ErrorCategory.UpstreamFailure, ErrorCodes.PythonServiceInvalidResponse)]
    public async Task Other_python_codes_are_classified_by_status(int status, string pythonCode, ErrorCategory category, string code)
    {
        var body = $$$"""{"error":{"code":"{{{pythonCode}}}","message":"m","request_id":"r"}}""";
        var client = ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Respond((HttpStatusCode)status, body)));

        var error = await Assert.ThrowsAsync<AmrException>(() => client.SimulateAsync(SimulateRequest, CancellationToken.None));

        AssertError(error, category, code);
    }

    [Theory]
    [InlineData(502)]
    [InlineData(503)]
    [InlineData(504)]
    public async Task A_gateway_failure_without_an_envelope_means_the_service_is_unavailable(int status)
    {
        var client = ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Respond((HttpStatusCode)status, "<html>upstream</html>", "text/html")));

        var error = await Assert.ThrowsAsync<AmrException>(() => client.GetModelAsync(CancellationToken.None));

        AssertError(error, ErrorCategory.DependencyUnavailable, ErrorCodes.PythonServiceUnavailable);
    }

    [Theory]
    [InlineData(301)]
    [InlineData(401)]
    [InlineData(404)]
    [InlineData(500)]
    public async Task Any_other_status_without_an_envelope_is_an_unexpected_response_or_internal_failure_never_success(int status)
    {
        var client = ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Respond((HttpStatusCode)status, "nope", "text/plain")));

        var error = await Assert.ThrowsAsync<AmrException>(() => client.GetModelAsync(CancellationToken.None));

        AssertError(error, ErrorCategory.UpstreamFailure, ErrorCodes.PythonServiceInvalidResponse);
    }

    [Fact]
    public async Task Python_messages_request_ids_and_internal_details_never_reach_the_public_error()
    {
        const string leaked = @"RuntimeError C:\secret\machine\path.csv at service/rollout.py line 42";
        var body = $$$"""{"error":{"code":"internal_error","message":"{{{leaked.Replace("\\", "\\\\", StringComparison.Ordinal)}}}","request_id":"python-request-123","details":[{"check":"horizon"}]}}""";
        var client = ClientFactory.Create(StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.InternalServerError, body)));

        var error = await Assert.ThrowsAsync<AmrException>(() => client.SimulateAsync(SimulateRequest, CancellationToken.None));

        var visible = $"{error.Message} {error.Code} {error}";
        Assert.DoesNotContain("secret", visible, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("rollout.py", visible, StringComparison.Ordinal);
        Assert.DoesNotContain("python-request-123", visible, StringComparison.Ordinal);
    }

    [Fact]
    public async Task A_connection_failure_is_python_service_unavailable_and_keeps_the_cause_for_logging_only()
    {
        var cause = new HttpRequestException("Connection refused", new SocketException((int)SocketError.ConnectionRefused));
        var client = ClientFactory.Create(StubHandler.Throwing(cause));

        var error = await Assert.ThrowsAsync<AmrException>(() => client.GetAntibioticsAsync(CancellationToken.None));

        AssertError(error, ErrorCategory.DependencyUnavailable, ErrorCodes.PythonServiceUnavailable);
        Assert.Same(cause, error.InnerException);
        Assert.DoesNotContain("refused", error.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task An_elapsed_request_timeout_is_python_service_timeout()
    {
        var client = ClientFactory.Create(StubHandler.Hanging(), requestTimeoutSeconds: 1);

        var error = await Assert.ThrowsAsync<AmrException>(() => client.SimulateAsync(SimulateRequest, CancellationToken.None));

        AssertError(error, ErrorCategory.DependencyUnavailable, ErrorCodes.PythonServiceTimeout);
    }

    [Fact]
    public async Task Health_uses_its_own_shorter_timeout()
    {
        var client = ClientFactory.Create(StubHandler.Hanging(), requestTimeoutSeconds: 60, healthTimeoutSeconds: 1);

        var started = DateTime.UtcNow;
        var error = await Assert.ThrowsAsync<AmrException>(() => client.GetHealthAsync(CancellationToken.None));

        AssertError(error, ErrorCategory.DependencyUnavailable, ErrorCodes.PythonServiceTimeout);
        Assert.True(DateTime.UtcNow - started < TimeSpan.FromSeconds(10));
    }

    [Fact]
    public async Task Caller_cancellation_propagates_to_the_http_request_and_is_not_reported_as_a_timeout()
    {
        var handler = StubHandler.Hanging();
        var client = ClientFactory.Create(handler);
        using var cancellation = new CancellationTokenSource();

        var pending = client.CompareAsync(CompareRequest, cancellation.Token);
        await cancellation.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => pending);
        Assert.True(handler.Requests.Single().Token.IsCancellationRequested);
    }

    [Fact]
    public async Task An_already_cancelled_token_never_reaches_the_service()
    {
        var handler = StubHandler.Returning(() => PythonFixtures.Fixture("health_200"));
        using var cancellation = new CancellationTokenSource();
        await cancellation.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => ClientFactory.Create(handler).GetHealthAsync(cancellation.Token));

        Assert.Equal(0, handler.CallCount);
    }

    [Fact]
    public async Task Simulation_and_comparison_are_never_retried_after_any_kind_of_failure()
    {
        var failures = new (string Name, Func<StubHandler> Make, int TimeoutSeconds)[]
        {
            ("503 model unavailable", () => StubHandler.Returning(() => PythonFixtures.Fixture("model_503_checkpoint_integrity_failure", HttpStatusCode.ServiceUnavailable)), 60),
            ("500 internal", () => StubHandler.Returning(() => PythonFixtures.Fixture("simulate_500_internal_error", HttpStatusCode.InternalServerError)), 60),
            ("502 gateway", () => StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.BadGateway, "bad gateway", "text/html")), 60),
            ("connection refused", () => StubHandler.Throwing(new HttpRequestException("refused")), 60),
            ("timeout", StubHandler.Hanging, 1),
            ("malformed", () => StubHandler.Returning(() => PythonFixtures.Respond(HttpStatusCode.OK, "{}")), 60),
        };

        foreach (var (name, make, timeoutSeconds) in failures)
        {
            var simulate = make();
            await Assert.ThrowsAsync<AmrException>(() => ClientFactory.Create(simulate, timeoutSeconds).SimulateAsync(SimulateRequest, CancellationToken.None));
            Assert.True(simulate.CallCount == 1, $"simulate was attempted {simulate.CallCount} times for {name}");

            var compare = make();
            await Assert.ThrowsAsync<AmrException>(() => ClientFactory.Create(compare, timeoutSeconds).CompareAsync(CompareRequest, CancellationToken.None));
            Assert.True(compare.CallCount == 1, $"compare was attempted {compare.CallCount} times for {name}");
        }
    }
}
