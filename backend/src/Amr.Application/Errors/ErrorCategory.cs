namespace Amr.Application.Errors;

/// <summary>Transport-neutral failure class; the API layer decides the HTTP status for each category.</summary>
public enum ErrorCategory
{
    InvalidRequest,
    NotFound,
    DependencyUnavailable,
    UpstreamFailure,
    Internal,
}
