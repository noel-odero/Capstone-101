using System.ComponentModel.DataAnnotations;

namespace Amr.Api.Authentication;

public sealed class RegisterRequest
{
    /// <summary>Ordinary ASCII addresses: plus-tags, dots, subdomains and long TLDs; no consecutive or edge dots, no quoted or internationalised forms.</summary>
    public const string EmailPattern = @"^(?!\.)(?!.*\.\.)[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}(?<!\.)@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9-]{2,63}$";

    [Required(ErrorMessage = "Enter your email address.")]
    [StringLength(254, ErrorMessage = "Use an email address of at most 254 characters.")]
    [RegularExpression(EmailPattern, ErrorMessage = "Enter a valid email address, such as name@example.org.")]
    public string? Email { get; init; }

    [Required(ErrorMessage = "Choose a password.")]
    [StringLength(PasswordRules.MaxLength, MinimumLength = PasswordRules.MinLength, ErrorMessage = "Use a password of 10 to 128 characters.")]
    public string? Password { get; init; }

    [StringLength(80, ErrorMessage = "Use a name of at most 80 characters.")]
    [RegularExpression(@"^[^\p{C}]*$", ErrorMessage = "The name cannot contain control characters.")]
    public string? DisplayName { get; init; }
}

public sealed class SignInRequest
{
    [Required(ErrorMessage = "Enter your email address.")]
    [StringLength(254)]
    public string? Email { get; init; }

    [Required(ErrorMessage = "Enter your password.")]
    [StringLength(PasswordRules.MaxLength)]
    public string? Password { get; init; }
}

public static class PasswordRules
{
    public const int MinLength = 10;
    public const int MaxLength = 128;
}

public sealed record SessionUserDto(string DisplayName, string Email);

/// <summary>The caller's session. The CSRF token is bound to the current identity, so it changes when someone signs in or out.</summary>
public sealed record SessionDto(bool IsAuthenticated, SessionUserDto? User, string CsrfToken);

public sealed record VerificationRequiredDto(bool VerificationRequired, string ChallengeToken, string Email,
    DateTimeOffset ExpiresAtUtc, DateTimeOffset ResendAvailableAtUtc);

public class ResendVerificationRequest
{
    [Required]
    [RegularExpression(@"^[A-Za-z0-9_-]{43}$")]
    public string? ChallengeToken { get; init; }
}

public sealed class VerifyEmailRequest : ResendVerificationRequest
{
    [Required]
    [RegularExpression(@"^[0-9]{6}$", ErrorMessage = "Enter the six-digit code from your email.")]
    public string? Code { get; init; }
}
