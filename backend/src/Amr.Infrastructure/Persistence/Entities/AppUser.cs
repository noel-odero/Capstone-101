namespace Amr.Infrastructure.Persistence.Entities;

/// <summary>A registered user. Runs refer to the user by id in their owner column; the password is stored only as a salted hash.</summary>
public sealed class AppUser
{
    public Guid Id { get; set; }

    public required string Email { get; set; }

    /// <summary>Trimmed, lower-case email; the unique key for sign-in and registration.</summary>
    public required string NormalizedEmail { get; set; }

    public required string DisplayName { get; set; }

    public required string PasswordHash { get; set; }

    /// <summary>Consecutive failed sign-ins since the last success or lockout.</summary>
    public int FailedSignInCount { get; set; }

    public DateTimeOffset? LockedUntilUtc { get; set; }

    public DateTimeOffset CreatedAtUtc { get; set; }

    public DateTimeOffset? EmailVerifiedAtUtc { get; set; }
}
