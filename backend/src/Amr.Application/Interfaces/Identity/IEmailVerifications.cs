namespace Amr.Application.Interfaces.Identity;

public sealed record PendingEmailVerification(
    string Email, string NormalizedEmail, string DisplayName, string PasswordHash, Guid? UserId,
    string TicketHash, string CodeHash, DateTimeOffset SentAtUtc, DateTimeOffset ExpiresAtUtc);

public enum EmailVerificationStatus { Succeeded, InvalidCode, Expired, TooManyAttempts }

public sealed record EmailVerificationOutcome(EmailVerificationStatus Status, UserAccount? User = null);

public interface IEmailVerifications
{
    // A single row per recipient makes limits survive restarts and concurrent requests.
    Task<bool> TryIssueAsync(PendingEmailVerification challenge, string? previousTicketHash, CancellationToken cancellationToken);
    Task<PendingEmailVerification?> FindAsync(string ticketHash, CancellationToken cancellationToken);
    Task<EmailVerificationOutcome> VerifyAsync(string ticketHash, string codeHash, CancellationToken cancellationToken);
    Task InvalidateAsync(string ticketHash, CancellationToken cancellationToken);
}
