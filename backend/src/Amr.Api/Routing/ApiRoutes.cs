namespace Amr.Api.Routing;

/// <summary>Single source for the versioned route templates; controllers must not repeat these strings.</summary>
public static class ApiRoutes
{
    public const string Version1 = "1.0";

    /// <summary>The route segment value for version 1, as in /api/v1/.</summary>
    public const string UrlVersion1 = "1";
    public const string Base = "api/v{version:apiVersion}";

    public const string Health = Base + "/health";
    public const string Model = Base + "/model";
    public const string Antibiotics = Base + "/antibiotics";
    public const string Profiles = Base + "/profiles";
    public const string Simulations = Base + "/simulations";
    public const string Comparisons = Base + "/comparisons";
    public const string Recommendations = Base + "/recommendations";
}
