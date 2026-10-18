using Amr.Api.Errors;
using Amr.Api.Routing;
using Amr.Application.DTOs.Profiles;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

[Route(ApiRoutes.Profiles)]
public sealed class ProfilesController(IProfileValidationService profiles) : ApiControllerBase
{
    /// <summary>Validates a seven-drug binary profile. A valid all-resistant profile is a normal terminal result (isTerminal true, no feasible actions).</summary>
    [HttpPost("validate")]
    [ProducesResponseType<ProfileValidationDto>(StatusCodes.Status200OK)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status422UnprocessableEntity, AmrProblemDetails.ContentType)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status503ServiceUnavailable, AmrProblemDetails.ContentType)]
    public async Task<ActionResult<ProfileValidationDto>> Validate(ValidateProfileRequest request, CancellationToken cancellationToken) =>
        await profiles.ValidateAsync(request, cancellationToken);
}
