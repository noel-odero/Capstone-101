using System.Security.Cryptography;
using Amr.Application.Interfaces.Identity;
using Amr.Infrastructure.Persistence.Entities;
using Microsoft.EntityFrameworkCore;

namespace Amr.Infrastructure.Persistence;

public sealed class EmailVerificationStore(AmrDbContext db, TimeProvider clock) : IEmailVerifications
{
    public async Task<bool> TryIssueAsync(PendingEmailVerification challenge, string? previousTicketHash, CancellationToken cancellationToken)
    {
        var cooldown = challenge.SentAtUtc.AddMinutes(-1);
        var window = challenge.SentAtUtc.AddHours(-1);
        var changed = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO email_verifications
              (normalized_email, email, display_name, password_hash, user_id, ticket_hash, code_hash,
               sent_at_utc, expires_at_utc, send_window_started_at_utc, send_count, failed_attempts)
            VALUES ({challenge.NormalizedEmail}, {challenge.Email}, {challenge.DisplayName}, {challenge.PasswordHash},
              {challenge.UserId}, {challenge.TicketHash}, {challenge.CodeHash}, {challenge.SentAtUtc},
              {challenge.ExpiresAtUtc}, {challenge.SentAtUtc}, 1, 0)
            ON CONFLICT (normalized_email) DO UPDATE SET
              email = EXCLUDED.email, display_name = EXCLUDED.display_name, password_hash = EXCLUDED.password_hash,
              user_id = EXCLUDED.user_id, ticket_hash = EXCLUDED.ticket_hash, code_hash = EXCLUDED.code_hash,
              sent_at_utc = EXCLUDED.sent_at_utc, expires_at_utc = EXCLUDED.expires_at_utc, failed_attempts = 0,
              send_window_started_at_utc = CASE WHEN email_verifications.send_window_started_at_utc <= {window}
                THEN EXCLUDED.sent_at_utc ELSE email_verifications.send_window_started_at_utc END,
              send_count = CASE WHEN email_verifications.send_window_started_at_utc <= {window}
                THEN 1 ELSE email_verifications.send_count + 1 END
            WHERE email_verifications.sent_at_utc <= {cooldown}
              AND (email_verifications.send_window_started_at_utc <= {window} OR email_verifications.send_count < 5)
              AND ({previousTicketHash}::text IS NULL OR email_verifications.ticket_hash = {previousTicketHash})
            """, cancellationToken);
        return changed == 1;
    }

    public async Task<PendingEmailVerification?> FindAsync(string ticketHash, CancellationToken cancellationToken)
    {
        var value = await db.EmailVerifications.AsNoTracking().SingleOrDefaultAsync(item => item.TicketHash == ticketHash, cancellationToken);
        return value?.PasswordHash is null || value.CodeHash is null ? null : new PendingEmailVerification(
            value.Email, value.NormalizedEmail, value.DisplayName, value.PasswordHash, value.UserId,
            ticketHash, value.CodeHash, value.SentAtUtc, value.ExpiresAtUtc);
    }

    public async Task<EmailVerificationOutcome> VerifyAsync(string ticketHash, string codeHash, CancellationToken cancellationToken)
    {
        await using var transaction = await db.Database.BeginTransactionAsync(cancellationToken);
        var challenge = await db.EmailVerifications.FromSqlInterpolated(
            $"SELECT * FROM email_verifications WHERE ticket_hash = {ticketHash} FOR UPDATE").AsTracking().SingleOrDefaultAsync(cancellationToken);
        if (challenge?.CodeHash is null || challenge.PasswordHash is null)
        {
            return new(EmailVerificationStatus.InvalidCode);
        }

        var now = clock.GetUtcNow();
        if (challenge.ExpiresAtUtc <= now)
        {
            return new(EmailVerificationStatus.Expired);
        }

        if (challenge.FailedAttempts >= 5)
        {
            return new(EmailVerificationStatus.TooManyAttempts);
        }

        if (!CryptographicOperations.FixedTimeEquals(Convert.FromHexString(challenge.CodeHash), Convert.FromHexString(codeHash)))
        {
            challenge.FailedAttempts++;
            await db.SaveChangesAsync(cancellationToken);
            await transaction.CommitAsync(cancellationToken);
            return new(challenge.FailedAttempts >= 5 ? EmailVerificationStatus.TooManyAttempts : EmailVerificationStatus.InvalidCode);
        }

        var user = await db.Users.AsTracking().SingleOrDefaultAsync(value => value.NormalizedEmail == challenge.NormalizedEmail, cancellationToken);
        if (challenge.UserId is { } userId)
        {
            // A code issued after password authentication cannot confirm another account or a changed password.
            if (user?.Id != userId || user.PasswordHash != challenge.PasswordHash)
            {
                return new(EmailVerificationStatus.InvalidCode);
            }
        }
        else if (user is not null)
        {
            return new(EmailVerificationStatus.InvalidCode);
        }
        else
        {
            user = new AppUser
            {
                Id = Guid.NewGuid(), Email = challenge.Email, NormalizedEmail = challenge.NormalizedEmail,
                DisplayName = challenge.DisplayName, PasswordHash = challenge.PasswordHash, CreatedAtUtc = now,
            };
            db.Users.Add(user);
        }

        user.EmailVerifiedAtUtc = now;
        user.FailedSignInCount = 0;
        user.LockedUntilUtc = null;
        challenge.TicketHash = null;
        challenge.CodeHash = null;
        challenge.PasswordHash = null;
        await db.SaveChangesAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);
        return new(EmailVerificationStatus.Succeeded, UserAccountStore.ToAccount(user));
    }

    public async Task InvalidateAsync(string ticketHash, CancellationToken cancellationToken) =>
        await db.EmailVerifications.Where(value => value.TicketHash == ticketHash).ExecuteUpdateAsync(set => set
            .SetProperty(value => value.TicketHash, (string?)null)
            .SetProperty(value => value.CodeHash, (string?)null)
            .SetProperty(value => value.PasswordHash, (string?)null), cancellationToken);
}
