namespace Amr.Application.Interfaces.Identity;

/// <summary>A registered user. The password hash is carried only so the caller can verify a sign-in; it is never serialized.</summary>
public sealed record UserAccount(Guid Id, string Email, string DisplayName, string PasswordHash, DateTimeOffset? LockedUntilUtc, DateTimeOffset? EmailVerifiedAtUtc = null);

/// <summary>Storage of email-and-password accounts. Emails are matched on their normalized (trimmed, lower-case) form.</summary>
public interface IUserAccounts
{
    Task<UserAccount?> FindByEmailAsync(string normalizedEmail, CancellationToken cancellationToken);

    /// <summary>Counts a failed sign-in atomically and locks the account for <paramref name="lockoutDuration"/> once the count reaches <paramref name="threshold"/>.</summary>
    Task RecordFailedSignInAsync(Guid userId, int threshold, TimeSpan lockoutDuration, CancellationToken cancellationToken);

    Task RecordSuccessfulSignInAsync(Guid userId, CancellationToken cancellationToken);
}
