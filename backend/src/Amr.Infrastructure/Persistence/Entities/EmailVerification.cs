namespace Amr.Infrastructure.Persistence.Entities;

public sealed class EmailVerification
{
    public required string NormalizedEmail { get; set; }
    public required string Email { get; set; }
    public required string DisplayName { get; set; }
    public string? PasswordHash { get; set; }
    public Guid? UserId { get; set; }
    public string? TicketHash { get; set; }
    public string? CodeHash { get; set; }
    public DateTimeOffset SentAtUtc { get; set; }
    public DateTimeOffset ExpiresAtUtc { get; set; }
    public DateTimeOffset SendWindowStartedAtUtc { get; set; }
    public int SendCount { get; set; }
    public int FailedAttempts { get; set; }
}
