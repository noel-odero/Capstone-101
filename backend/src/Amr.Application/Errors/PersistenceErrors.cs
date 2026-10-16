namespace Amr.Application.Errors;

/// <summary>
/// Failures to store a run that the scientific service already completed. The message says so: the run executed upstream
/// but has no public record, so the client must not assume a result was saved.
/// </summary>
public static class PersistenceErrors
{
    public static AmrException Unavailable(Exception? innerException = null) => new(
        ErrorCategory.DependencyUnavailable,
        ErrorCodes.DatabaseUnavailable,
        "The simulation ran but its result could not be saved because the database is unavailable. No record exists for this run.",
        innerException);

    public static AmrException Failed(Exception? innerException = null) => new(
        ErrorCategory.Internal,
        ErrorCodes.PersistenceFailed,
        "The simulation ran but its result could not be saved. No record exists for this run.",
        innerException);

    public static AmrException ReadFailed(Exception? innerException = null) => new(
        ErrorCategory.DependencyUnavailable,
        ErrorCodes.DatabaseUnavailable,
        "Stored results are unavailable because the database could not be read.",
        innerException);
}
