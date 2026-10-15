using System.Text.Json;
using Amr.Api.Extensions;
using Amr.Application.Errors;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using Microsoft.AspNetCore.WebUtilities;

namespace Amr.Api.Errors;

/// <summary>The one place that shapes RFC 9457 problem responses: stable code, correlation id, and the status for each error category.</summary>
public static class AmrProblemDetails
{
    public const string ContentType = "application/problem+json";
    public const string CodeKey = "code";
    public const string CorrelationIdKey = "correlationId";
    private const string TypePrefix = "urn:amr:problem:";

    public static int StatusFor(ErrorCategory category) => category switch
    {
        ErrorCategory.InvalidRequest => StatusCodes.Status422UnprocessableEntity,
        ErrorCategory.NotFound => StatusCodes.Status404NotFound,
        ErrorCategory.DependencyUnavailable => StatusCodes.Status503ServiceUnavailable,
        ErrorCategory.UpstreamFailure => StatusCodes.Status502BadGateway,
        ErrorCategory.Internal => StatusCodes.Status500InternalServerError,
        _ => throw new ArgumentOutOfRangeException(nameof(category), category, "Unmapped error category."),
    };

    public static ProblemDetails Create(HttpContext context, int status, string code, string detail) =>
        Decorate(
            new ProblemDetails
            {
                Status = status,
                Title = ReasonPhrases.GetReasonPhrase(status),
                Detail = detail,
            },
            context,
            code);

    /// <summary>Adds type, code, instance and correlation id. A code already present is kept; otherwise one is derived from the status.</summary>
    public static ProblemDetails Decorate(ProblemDetails problem, HttpContext context, string? code = null)
    {
        var resolved = code
            ?? (problem.Extensions.TryGetValue(CodeKey, out var existing) ? existing as string : null)
            ?? CodeForStatus(problem.Status ?? StatusCodes.Status500InternalServerError);

        problem.Extensions[CodeKey] = resolved;
        problem.Extensions[CorrelationIdKey] = context.GetCorrelationId();
        problem.Type = TypePrefix + resolved;
        problem.Instance ??= context.Request.Path;
        return problem;
    }

    /// <summary>422 with every message the caller can act on. Parse errors carry framework exception text, so they get a generic message.</summary>
    public static IActionResult FromModelState(ActionContext context)
    {
        var errors = context.ModelState
            .Where(entry => entry.Value is { Errors.Count: > 0 })
            .SelectMany(entry => entry.Value!.Errors.Select(error => (Key: NormalizeKey(entry.Key), Message: SafeMessage(entry.Key, error))))
            .GroupBy(item => item.Key)
            .ToDictionary(group => group.Key, group => group.Select(item => item.Message).Distinct().ToArray());

        var problem = new ValidationProblemDetails(errors)
        {
            Status = StatusCodes.Status422UnprocessableEntity,
            Title = "One or more validation errors occurred.",
        };
        Decorate(problem, context.HttpContext, ErrorCodes.ValidationFailed);

        return new UnprocessableEntityObjectResult(problem) { ContentTypes = { ContentType } };
    }

    private static string CodeForStatus(int status) => status switch
    {
        StatusCodes.Status400BadRequest => "bad_request",
        StatusCodes.Status404NotFound => ErrorCodes.NotFound,
        StatusCodes.Status405MethodNotAllowed => "method_not_allowed",
        StatusCodes.Status415UnsupportedMediaType => "unsupported_media_type",
        >= 500 => ErrorCodes.InternalError,
        _ => "http_error",
    };

    private static string SafeMessage(string key, ModelError error) =>
        key.StartsWith('$') || error.Exception is not null || string.IsNullOrWhiteSpace(error.ErrorMessage)
            ? "The value is not valid."
            : error.ErrorMessage;

    private static string NormalizeKey(string key)
    {
        var normalized = string.Join('.', key.TrimStart('$', '.').Split('.').Select(JsonNamingPolicy.CamelCase.ConvertName));
        return normalized.Length == 0 ? "request" : normalized;
    }
}
