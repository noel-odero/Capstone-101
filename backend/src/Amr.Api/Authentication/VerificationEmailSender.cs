using System.Net.Mail;
using Amr.Application.Errors;
using Azure;
using Azure.Communication.Email;
using Microsoft.Extensions.Options;

namespace Amr.Api.Authentication;

public interface IVerificationEmailSender
{
    void EnsureConfigured();
    Task SendAsync(string recipient, string code, CancellationToken cancellationToken);
}

public sealed class VerificationEmailOptions
{
    public string? ConnectionString { get; init; }
    public string? SenderAddress { get; init; }
}

public sealed partial class AzureVerificationEmailSender(IOptions<VerificationEmailOptions> options,
    ILogger<AzureVerificationEmailSender> logger) : IVerificationEmailSender
{
    public void EnsureConfigured()
    {
        if (string.IsNullOrWhiteSpace(options.Value.ConnectionString) ||
            !MailAddress.TryCreate(options.Value.SenderAddress, out var address) || address.DisplayName.Length != 0)
        {
            throw Unavailable();
        }
    }

    public async Task SendAsync(string recipient, string code, CancellationToken cancellationToken)
    {
        EnsureConfigured();
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(20));
        try
        {
            var clientOptions = new EmailClientOptions();
            clientOptions.Retry.MaxRetries = 0;
            clientOptions.Diagnostics.IsLoggingContentEnabled = false;
            var client = new EmailClient(options.Value.ConnectionString, clientOptions);
            var content = new EmailContent("Your StewardLab verification code")
            {
                PlainText = $"Your StewardLab verification code is {code}. It expires in 10 minutes. Enter it in the browser where you requested it. Never share this code. If you did not request it, ignore this email.",
                Html = $"<html><body style=\"font-family:Arial,sans-serif;color:#222\"><h2>Verify your email</h2><p>Your StewardLab code:</p><p style=\"font-size:32px;letter-spacing:8px;font-weight:bold\">{code}</p><p>Expires in 10 minutes. Enter it in the browser where you requested it.</p><p>Never share this code. If you did not request it, ignore this email.</p></body></html>",
            };
            await client.SendAsync(WaitUntil.Started,
                new EmailMessage(options.Value.SenderAddress, recipient, content), timeout.Token);
        }
        catch (Exception exception) when (exception is RequestFailedException or ArgumentException or InvalidOperationException or FormatException ||
            exception is OperationCanceledException && !cancellationToken.IsCancellationRequested)
        {
            var azureFailure = exception as RequestFailedException;
            var errorCode = azureFailure?.ErrorCode;
            var safeCode = errorCode is { Length: > 0 and <= 100 } &&
                errorCode.All(character => char.IsAsciiLetterOrDigit(character) || character is '_' or '-' or '.')
                ? errorCode : "unavailable";
            LogDeliveryFailure(logger, azureFailure?.Status, safeCode, exception.GetType().Name);
            throw Unavailable();
        }
    }

    private static AmrException Unavailable() => new(ErrorCategory.DependencyUnavailable, ErrorCodes.VerificationUnavailable,
        "Verification email is temporarily unavailable. Please try again shortly.");

    [LoggerMessage(Level = LogLevel.Warning, Message = "Verification email could not be submitted to Azure. Status: {Status}; code: {ErrorCode}; failure: {FailureType}.")]
    private static partial void LogDeliveryFailure(ILogger logger, int? status, string errorCode, string failureType);
}
