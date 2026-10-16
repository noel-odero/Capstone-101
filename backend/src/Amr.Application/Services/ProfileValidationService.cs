using Amr.Application.DTOs.Profiles;
using Amr.Application.Interfaces.Clients;
using Amr.Application.Interfaces.Services;
using Amr.Application.Mappings;

namespace Amr.Application.Services;

/// <summary>
/// Profile shape is validated once, at the API boundary, by the DTO attributes. This service trusts that and
/// forwards the profile; Python remains the authoritative backstop, and a rejection there surfaces as 422.
/// </summary>
public sealed class ProfileValidationService(IPythonServiceClient python) : IProfileValidationService
{
    public async Task<ProfileValidationDto> ValidateAsync(ValidateProfileRequest request, CancellationToken cancellationToken) =>
        (await python.ValidateProfileAsync(request.ResistanceProfile, cancellationToken)).ToDto();
}
