namespace Amr.Api.Authentication;

/// <summary>Authentication settings, bound from the "Auth" section.</summary>
public sealed class AuthOptions
{
    public const string SectionName = "Auth";

    /// <summary>Absolute lifetime of a signed-in session; there is no sliding renewal.</summary>
    public int SessionHours { get; init; } = 8;

    /// <summary>Consecutive wrong passwords that lock an account.</summary>
    public int MaxFailedSignIns { get; init; } = 5;

    public int LockoutMinutes { get; init; } = 15;

    /// <summary>Sign-in and registration requests allowed per client address per minute.</summary>
    public int AttemptsPerMinute { get; init; } = 20;
}
