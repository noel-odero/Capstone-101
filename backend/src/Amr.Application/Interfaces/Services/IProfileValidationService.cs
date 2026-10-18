using Amr.Application.DTOs.Profiles;

namespace Amr.Application.Interfaces.Services;

public interface IProfileValidationService
{
    Task<ProfileValidationDto> ValidateAsync(ValidateProfileRequest request, CancellationToken cancellationToken);
}
