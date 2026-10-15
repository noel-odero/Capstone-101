namespace Amr.Application.Errors;

/// <summary>Errors for a scientific-service response that cannot be trusted or understood. Messages are safe for clients.</summary>
public static class UpstreamErrors
{
    public static AmrException InvalidResponse(Exception? innerException = null) => new(
        ErrorCategory.UpstreamFailure,
        ErrorCodes.PythonServiceInvalidResponse,
        "The scientific service returned an unexpected response.",
        innerException);
}
