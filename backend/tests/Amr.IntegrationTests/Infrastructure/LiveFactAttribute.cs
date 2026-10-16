namespace Amr.IntegrationTests.Infrastructure;

/// <summary>
/// Runs only when AMR_PYTHON_URL points at a running Python service; otherwise reported as skipped. When
/// AMR_REQUIRE_LIVE is true (the CI job that starts the service) a missing URL is a failure, never a skip.
/// </summary>
public sealed class LiveFactAttribute : FactAttribute
{
    public const string UrlVariable = "AMR_PYTHON_URL";
    public const string RequireVariable = "AMR_REQUIRE_LIVE";

    public LiveFactAttribute()
    {
        if (!Required && Environment.GetEnvironmentVariable(UrlVariable) is null)
        {
            Skip = $"Set {UrlVariable} (for example http://127.0.0.1:8000) to run against a live Python service.";
        }
    }

    public static bool Required => string.Equals(Environment.GetEnvironmentVariable(RequireVariable), "true", StringComparison.OrdinalIgnoreCase);

    /// <exception cref="InvalidOperationException">The live job requires a service but no URL was provided.</exception>
    public static string? Url => Environment.GetEnvironmentVariable(UrlVariable) is { Length: > 0 } url
        ? url
        : Required ? throw new InvalidOperationException($"{RequireVariable} is true but {UrlVariable} is not set.") : null;
}
