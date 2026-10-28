using Amr.Application.Errors;
using Amr.Application.Interfaces.Identity;
using Amr.Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Amr.Infrastructure.Persistence;

/// <summary>PostgreSQL storage of user accounts. The email uniqueness rule lives in the database, so concurrent registrations cannot both succeed.</summary>
public sealed class UserAccountStore(AmrDbContext db, TimeProvider clock) : IUserAccounts
{
    public async Task<UserAccount?> FindByEmailAsync(string normalizedEmail, CancellationToken cancellationToken)
    {
        try
        {
            var user = await db.Users.SingleOrDefaultAsync(candidate => candidate.NormalizedEmail == normalizedEmail, cancellationToken);
            return user is null ? null : ToAccount(user);
        }
        catch (Exception exception) when (IsDatabaseFailure(exception, cancellationToken))
        {
            throw Translate(exception);
        }
    }

    public async Task RecordFailedSignInAsync(Guid userId, int threshold, TimeSpan lockoutDuration, CancellationToken cancellationToken)
    {
        try
        {
            var lockedUntil = clock.GetUtcNow() + lockoutDuration;
            await db.Users.Where(user => user.Id == userId)
                .ExecuteUpdateAsync(set => set.SetProperty(user => user.FailedSignInCount, user => user.FailedSignInCount + 1), cancellationToken);
            await db.Users.Where(user => user.Id == userId && user.FailedSignInCount >= threshold)
                .ExecuteUpdateAsync(
                    set => set.SetProperty(user => user.LockedUntilUtc, lockedUntil).SetProperty(user => user.FailedSignInCount, 0),
                    cancellationToken);
        }
        catch (Exception exception) when (IsDatabaseFailure(exception, cancellationToken))
        {
            throw Translate(exception);
        }
    }

    public async Task RecordSuccessfulSignInAsync(Guid userId, CancellationToken cancellationToken)
    {
        try
        {
            await db.Users.Where(user => user.Id == userId)
                .ExecuteUpdateAsync(
                    set => set.SetProperty(user => user.FailedSignInCount, 0).SetProperty(user => user.LockedUntilUtc, (DateTimeOffset?)null),
                    cancellationToken);
        }
        catch (Exception exception) when (IsDatabaseFailure(exception, cancellationToken))
        {
            throw Translate(exception);
        }
    }

    internal static UserAccount ToAccount(AppUser user) => new(user.Id, user.Email, user.DisplayName, user.PasswordHash, user.LockedUntilUtc, user.EmailVerifiedAtUtc);

    private static bool IsDatabaseFailure(Exception exception, CancellationToken cancellationToken) =>
        exception is not AmrException && !(exception is OperationCanceledException && cancellationToken.IsCancellationRequested);

    private static Exception Translate(Exception exception) =>
        PersistenceFailureClassifier.IsUnavailable(exception) ? PersistenceErrors.AccountsUnavailable(exception) : exception;
}
