namespace Amr.Application.Errors;

/// <summary>An expected failure with a stable code. The message must be safe to show to API clients.</summary>
public sealed class AmrException(ErrorCategory category, string code, string message, Exception? innerException = null)
    : Exception(message, innerException)
{
    public ErrorCategory Category { get; } = category;

    public string Code { get; } = code;
}
