namespace Amr.Application.Errors;

/// <summary>The one explicit answer for operations that need stored results, which do not exist until persistence is implemented.</summary>
public static class PersistenceNotAvailable
{
    public static AmrException Error() => new(
        ErrorCategory.NotImplemented,
        ErrorCodes.PersistenceNotAvailable,
        "Stored results are not available yet because persistence has not been implemented.");
}
