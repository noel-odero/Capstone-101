using Amr.Application.Validators;

namespace Amr.Application.DTOs.Profiles;

public sealed record ValidateProfileRequest
{
    /// <summary>Seven values in canonical antibiotic order; 0 susceptible, 1 resistant. Unknown values are not supported.</summary>
    [ResistanceProfile]
    public required IReadOnlyList<int> ResistanceProfile { get; init; }
}
