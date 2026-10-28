using Amr.Application.Interfaces.Identity;

namespace Amr.Api.Authentication;

public enum AccountStatus
{
    Succeeded,
    InvalidCredentials,
    LockedOut,
    EmailUnverified,
}

public sealed record AccountOutcome(AccountStatus Status, UserAccount? User = null, TimeSpan? RetryAfter = null);

/// <summary>Password authentication and account lockout, before any email-verification or session step.</summary>
public sealed class AccountService(IUserAccounts accounts, PasswordService passwords, AuthOptions options, TimeProvider clock)
{
    public static string NormalizeEmail(string email) => email.Trim().ToLowerInvariant();

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
        return new AccountOutcome(user.EmailVerifiedAtUtc is null ? AccountStatus.EmailUnverified : AccountStatus.Succeeded, user);
    }
}
