using System.ComponentModel.DataAnnotations;

namespace Amr.Infrastructure.Python;

/// <summary>Connection settings for the private Python service, bound from the "PythonService" configuration section.</summary>
public sealed class PythonServiceOptions : IValidatableObject
{
    public const string SectionName = "PythonService";

    [Required]
    public Uri? BaseUrl { get; init; }

    [Range(1, 60)]
    public int ConnectTimeoutSeconds { get; init; } = 5;

    [Range(1, 600)]
    public int RequestTimeoutSeconds { get; init; } = 60;

    [Range(1, 60)]
    public int HealthTimeoutSeconds { get; init; } = 3;

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (BaseUrl is not null && (!BaseUrl.IsAbsoluteUri || BaseUrl.Scheme is not ("http" or "https")))
        {
            yield return new ValidationResult("BaseUrl must be an absolute http or https URL.", [nameof(BaseUrl)]);
        }
    }
}
