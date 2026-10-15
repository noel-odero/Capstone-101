using System.Net;
using System.Text.Json;
using Amr.Application.Errors;
using Amr.Application.PythonContracts;
using Microsoft.Extensions.Logging;

namespace Amr.Infrastructure.Python;

/// <summary>
/// The single place that turns Python failures into public application errors. Python messages, request ids and
/// details are logged here and never copied into the returned exception.
/// </summary>
public sealed partial class PythonServiceErrorMapper(ILogger<PythonServiceErrorMapper> logger)
{
    public AmrException FromResponse(HttpStatusCode status, string body)
    {
        var envelope = TryReadEnvelope(body);
        if (envelope is null)
        {
            LogUnstructuredResponse(logger, (int)status);
            return status is HttpStatusCode.BadGateway or HttpStatusCode.ServiceUnavailable or HttpStatusCode.GatewayTimeout
                ? Unavailable(innerException: null)
                : InvalidResponse(innerException: null);
        }

        LogPythonError(logger, (int)status, envelope.Error.Code, envelope.Error.RequestId);
        return envelope.Error.Code switch
        {
            PythonErrorCodes.InvalidContext or PythonErrorCodes.RequestValidationError => new AmrException(
                ErrorCategory.InvalidRequest, ErrorCodes.ValidationFailed, "The scientific service rejected the request."),
            PythonErrorCodes.ModelNotLoaded
                or PythonErrorCodes.CheckpointIntegrityFailure
                or PythonErrorCodes.ModelContractMismatch
                or PythonErrorCodes.ModelOrDataUnavailable => new AmrException(
                ErrorCategory.DependencyUnavailable, ErrorCodes.ModelUnavailable, "The frozen model is not available."),
            PythonErrorCodes.ComparisonContractViolation => ComparisonErrors.ContractViolation(),
            _ when (int)status >= 500 => new AmrException(
                ErrorCategory.Internal, ErrorCodes.InternalError, "The scientific service failed to complete the request."),
            _ => InvalidResponse(innerException: null),
        };
    }

    public static AmrException Timeout() => new(
        ErrorCategory.DependencyUnavailable, ErrorCodes.PythonServiceTimeout, "The scientific service did not respond in time.");

    public static AmrException Unavailable(Exception? innerException) => new(
        ErrorCategory.DependencyUnavailable, ErrorCodes.PythonServiceUnavailable, "The scientific service is unavailable.", innerException);

    public static AmrException InvalidResponse(Exception? innerException) => UpstreamErrors.InvalidResponse(innerException);

    private static PythonErrorEnvelope? TryReadEnvelope(string body)
    {
        try
        {
            return JsonSerializer.Deserialize<PythonErrorEnvelope>(body, PythonJson.Options);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    [LoggerMessage(Level = LogLevel.Warning, Message = "Python service returned {Status} with code {PythonCode} (python request {PythonRequestId}).")]
    private static partial void LogPythonError(ILogger logger, int status, string pythonCode, string pythonRequestId);

    [LoggerMessage(Level = LogLevel.Warning, Message = "Python service returned {Status} without a recognizable error envelope.")]
    private static partial void LogUnstructuredResponse(ILogger logger, int status);
}
