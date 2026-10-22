using Microsoft.AspNetCore.Authorization;
using Amr.Api.Errors;
using Amr.Api.Routing;
using Amr.Application.DTOs.Health;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

[Route(ApiRoutes.Health)]
[AllowAnonymous]
public sealed class HealthController(IHealthService health) : ApiControllerBase
{
    /// <summary>Readiness: 200 only when the Python service and its verified model are healthy, otherwise 503 with the same report.</summary>
    [HttpGet]
    [ProducesResponseType<HealthDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<HealthDto>(StatusCodes.Status503ServiceUnavailable)]
    public async Task<ActionResult<HealthDto>> GetReadiness(CancellationToken cancellationToken)
    {
        var report = await health.GetHealthAsync(cancellationToken);
        if (report.Ready)
        {
            return report;
        }

        return StatusCode(StatusCodes.Status503ServiceUnavailable, report);
    }

    /// <summary>Liveness: the process answers; no dependency is touched.</summary>
    [HttpGet("live")]
    [ProducesResponseType<HealthDto>(StatusCodes.Status200OK)]
    public ActionResult<HealthDto> GetLiveness() => health.GetLiveness();
}
