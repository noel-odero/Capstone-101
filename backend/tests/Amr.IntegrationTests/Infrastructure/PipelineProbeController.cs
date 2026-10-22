using Amr.Api.Extensions;
using Amr.Api.Routing;
using Amr.Application.DTOs.Profiles;
using Amr.Application.DTOs.Simulations;
using Amr.Application.Errors;
using Asp.Versioning;
using Microsoft.AspNetCore.Mvc;

#pragma warning disable CA1822 // MVC actions are instance methods even when they use no instance state.

namespace Amr.IntegrationTests.Infrastructure;

/// <summary>Test-only endpoints for versioning, binding, validation and error handling.</summary>
[ApiController]
[ApiVersion(ApiRoutes.Version1)]
[Route(ApiRoutes.Base + "/pipeline-probe")]
public sealed class PipelineProbeController : ControllerBase
{
    public const string SafeMessage = "Safe probe message.";
    public const string SecretMessage = @"secret C:\private\path\appsettings.json";

    [HttpGet("ok")]
    public IActionResult Get() => Ok(new { correlationId = HttpContext.GetCorrelationId() });

    [HttpPost("profile")]
    public IActionResult Profile([FromBody] ValidateProfileRequest request) => Ok(request);

    [HttpPost("simulation")]
    public IActionResult Simulation([FromBody] CreateSimulationRequest request) => Ok(request);

    [HttpGet("recent")]
    public IActionResult Recent([FromQuery] RecentRunsQuery query) => Ok(query);

    [HttpGet("fail/{category}")]
    public IActionResult Fail(ErrorCategory category) => throw new AmrException(category, "probe_failure", SafeMessage);

    [HttpGet("crash")]
    public IActionResult Crash() => throw new InvalidOperationException(SecretMessage);
}
