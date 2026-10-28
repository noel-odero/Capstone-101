using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Amr.Application.Errors;
using Amr.Application.Interfaces.Identity;
using Microsoft.AspNetCore.WebUtilities;

namespace Amr.Api.Authentication;

public sealed class EmailVerificationService(IEmailVerifications verifications, IUserAccounts accounts,
    PasswordService passwords, IVerificationEmailSender sender, TimeProvider clock)
{
    public async Task<VerificationRequiredDto> RegisterAsync(RegisterRequest request, CancellationToken cancellationToken)
    {
        sender.EnsureConfigured();
        var email = request.Email!.Trim();
        var normalized = AccountService.NormalizeEmail(email);
        var name = string.IsNullOrWhiteSpace(request.DisplayName) ? email[..email.IndexOf('@')] : request.DisplayName.Trim();
        name = name[..Math.Min(name.Length, 80)];
        var passwordHash = passwords.Hash(request.Password!);
        if (await accounts.FindByEmailAsync(normalized, cancellationToken) is not null)
        {
            // Match the response shape without allowing registration to overwrite an existing password.
            return Describe(WebEncoders.Base64UrlEncode(RandomNumberGenerator.GetBytes(32)), email, clock.GetUtcNow());
        }

        return await IssueAsync(email, normalized, name, passwordHash, null, null, cancellationToken);
    }

    public Task<VerificationRequiredDto> ForExistingAccountAsync(UserAccount user, CancellationToken cancellationToken) =>
        IssueAsync(user.Email, AccountService.NormalizeEmail(user.Email), user.DisplayName, user.PasswordHash, user.Id, null, cancellationToken);

    public async Task<VerificationRequiredDto> ResendAsync(string ticket, CancellationToken cancellationToken)
    {
        var ticketHash = Hash(ticket);
        var previous = await verifications.FindAsync(ticketHash, cancellationToken);
        if (previous is null)
        {
            throw InvalidCode();
        }

        return await IssueAsync(previous.Email, previous.NormalizedEmail, previous.DisplayName, previous.PasswordHash,
            previous.UserId, ticketHash, cancellationToken);
    }

    public async Task<UserAccount> VerifyAsync(string ticket, string code, CancellationToken cancellationToken)
    {
        var result = await verifications.VerifyAsync(Hash(ticket), Hash(ticket + ":" + code), cancellationToken);
        return result.Status switch
        {
            EmailVerificationStatus.Succeeded when result.User is not null => result.User,
            EmailVerificationStatus.Expired => throw new AmrException(ErrorCategory.InvalidRequest, ErrorCodes.VerificationCodeExpired, "This code has expired. Request a new code."),
            EmailVerificationStatus.TooManyAttempts => throw new AmrException(ErrorCategory.InvalidRequest, ErrorCodes.InvalidVerificationCode, "Too many incorrect codes. Request a new code."),
            _ => throw InvalidCode(),
        };
    }

    private async Task<VerificationRequiredDto> IssueAsync(string email, string normalized, string name, string passwordHash,
        Guid? userId, string? previousTicketHash, CancellationToken cancellationToken)
    {
        sender.EnsureConfigured();
        var now = clock.GetUtcNow();
        var ticket = WebEncoders.Base64UrlEncode(RandomNumberGenerator.GetBytes(32));
        var code = RandomNumberGenerator.GetInt32(1_000_000).ToString("D6", CultureInfo.InvariantCulture);
        var challenge = new PendingEmailVerification(email, normalized, name, passwordHash, userId,
            Hash(ticket), Hash(ticket + ":" + code), now, now.AddMinutes(10));
        if (!await verifications.TryIssueAsync(challenge, previousTicketHash, cancellationToken))
        {
            throw new AmrException(ErrorCategory.InvalidRequest, ErrorCodes.VerificationRateLimited,
                "Please wait before requesting another code. You can request one per minute and up to five per hour.");
        }

        try
        {
            await sender.SendAsync(email, code, cancellationToken);
        }
        catch
        {
            await verifications.InvalidateAsync(challenge.TicketHash, CancellationToken.None);
            throw;
        }

        return Describe(ticket, email, now);
    }

    private static VerificationRequiredDto Describe(string ticket, string email, DateTimeOffset now) =>
        new(true, ticket, email, now.AddMinutes(10), now.AddMinutes(1));

    private static string Hash(string value) => Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(value)));

    private static AmrException InvalidCode() => new(ErrorCategory.InvalidRequest, ErrorCodes.InvalidVerificationCode,
        "The code is incorrect or no longer valid. Check the latest email or request a new code.");
}
