namespace Amr.Infrastructure.Python;

/// <summary>Routes of the private Python service, relative to its base address (no leading slash, so a path base is preserved).</summary>
internal static class PythonEndpoints
{
    public const string Health = "internal/health";
    public const string Model = "internal/model";
    public const string Antibiotics = "internal/antibiotics";
    public const string ValidateProfile = "internal/profiles/validate";
    public const string Simulate = "internal/simulate";
    public const string Compare = "internal/compare";
}
