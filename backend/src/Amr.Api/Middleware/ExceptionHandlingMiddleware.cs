using Amr.Api.Errors;
using Amr.Application.Errors;

namespace Amr.Api.Middleware;

/// <summary>Turns exceptions into safe problem responses. Details are logged with the correlation id; only expected AmrException messages reach the client.</summary>
public sealed partial class ExceptionHandlingMiddleware(RequestDelegate next, ILogger<ExceptionHandlingMiddleware> logger)
{
    private const int ClientClosedRequest = 499;
    private const string UnexpectedErrorDetail = "An unexpected error occurred. Report the correlation id if the problem persists.";

    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await next(context);
        }
        catch (OperationCanceledException) when (context.RequestAborted.IsCancellationRequested)
        {
            LogClientClosedRequest(logger);
            context.Response.StatusCode = ClientClosedRequest;
        }
        catch (Exception exception) when (!context.Response.HasStarted)
        {
            await WriteProblemAsync(context, exception);
        }
    }

    private async Task WriteProblemAsync(HttpContext context, Exception exception)
    {
        var problem = exception is AmrException known
            ? AmrProblemDetails.Create(context, AmrProblemDetails.StatusFor(known.Category), known.Code, known.Message)
            : AmrProblemDetails.Create(context, StatusCodes.Status500InternalServerError, ErrorCodes.InternalError, UnexpectedErrorDetail);

        if (exception is AmrException)
        {
            LogExpectedFailure(logger, exception, (string)problem.Extensions[AmrProblemDetails.CodeKey]!, problem.Status!.Value);
        }
        else
        {
            LogUnexpectedFailure(logger, exception, context.Request.Method, context.Request.Path);
        }

        context.Response.StatusCode = problem.Status!.Value;
        await context.Response.WriteAsJsonAsync(problem, options: null, contentType: AmrProblemDetails.ContentType, context.RequestAborted);
    }

    [LoggerMessage(Level = LogLevel.Information, Message = "The client closed the request before it completed.")]
    private static partial void LogClientClosedRequest(ILogger logger);

    [LoggerMessage(Level = LogLevel.Warning, Message = "Request failed with {ErrorCode} ({Status}).")]
    private static partial void LogExpectedFailure(ILogger logger, Exception exception, string errorCode, int status);

    [LoggerMessage(Level = LogLevel.Error, Message = "Unhandled exception while processing {Method} {Path}.")]
    private static partial void LogUnexpectedFailure(ILogger logger, Exception exception, string method, PathString path);
}
