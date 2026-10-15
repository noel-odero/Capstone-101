namespace Amr.IntegrationTests.Infrastructure;

/// <summary>Runs only when AMR_PYTHON_URL points at a running Python service; otherwise reported as skipped.</summary>
public sealed class LiveFactAttribute : FactAttribute
{
    public const string UrlVariable = "AMR_PYTHON_URL";

    public LiveFactAttribute()
    {
        if (Url is null)
        {
            Skip = $"Set {UrlVariable} (for example http://127.0.0.1:8000) to run against a live Python service.";
        }
    }

    public static string? Url => Environment.GetEnvironmentVariable(UrlVariable);
}
