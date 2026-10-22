using Amr.Application.Interfaces.Identity;

namespace Amr.Api.Authentication;

public enum AccountStatus
{
    Succeeded,
    InvalidCredentials,
    LockedOut,
    EmailTaken,
}

public sealed record AccountOutcome(AccountStatus Status, UserAccount? User = null, TimeSpan? RetryAfter = null);

/// <summary>Registration and sign-in rules. Controllers translate HTTP; this decides who gets in.</summary>
public sealed class AccountService(IUserAccounts accounts, PasswordService passwords, AuthOptions options, TimeProvider clock)
{
    private const int MaxDisplayNameLength = 80;

    public static string NormalizeEmail(string email) => email.Trim().ToLowerInvariant();

    public async Task<AccountOutcome> RegisterAsync(string email, string password, string? displayName, CancellationToken cancellationToken)
    {
        var trimmed = email.Trim();
        var name = string.IsNullOrWhiteSpace(displayName) ? LocalPart(trimmed) : displayName.Trim();
        var created = await accounts.CreateAsync(trimmed, NormalizeEmail(trimmed), name, passwords.Hash(password), cancellationToken);
        return created is null ? new AccountOutcome(AccountStatus.EmailTaken) : new AccountOutcome(AccountStatus.Succeeded, created);
    }

    public async Task<AccountOutcome> SignInAsync(string email, string password, CancellationToken cancellationToken)
    {
        var user = await accounts.FindByEmailAsync(NormalizeEmail(email), cancellationToken);
        if (user is null)
        {
            passwords.VerifyAgainstDecoy(password);
            return new AccountOutcome(AccountStatus.InvalidCredentials);
        }

        var now = clock.GetUtcNow();
        if (user.LockedUntilUtc is { } lockedUntil && lockedUntil > now)
        {
            return new AccountOutcome(AccountStatus.LockedOut, RetryAfter: lockedUntil - now);
        }

        if (!passwords.Verify(user.PasswordHash, password))
        {
            await accounts.RecordFailedSignInAsync(user.Id, options.MaxFailedSignIns, TimeSpan.FromMinutes(options.LockoutMinutes), cancellationToken);
            return new AccountOutcome(AccountStatus.InvalidCredentials);
        }

        await accounts.RecordSuccessfulSignInAsync(user.Id, cancellationToken);
        return new AccountOutcome(AccountStatus.Succeeded, user);
    }

    private static string LocalPart(string email)
    {
        var local = email[..email.IndexOf('@')];
        return local.Length <= MaxDisplayNameLength ? local : local[..MaxDisplayNameLength];
    }
}
