using Amr.Api.Middleware;

namespace Amr.Api.Extensions;

public static class ApplicationBuilderExtensions
{
    /// <summary>Correlation id first so every later log line and error carries it, then exception handling, then status-code problem bodies.</summary>
    public static IApplicationBuilder UseAmrMiddleware(this IApplicationBuilder app) =>
        app.UseMiddleware<CorrelationIdMiddleware>()
            .UseMiddleware<ExceptionHandlingMiddleware>()
            .UseStatusCodePages();
}
