namespace Amr.Api.Extensions;

public static class CorrelationIdExtensions
{
    internal const string CorrelationIdItemKey = "Amr.CorrelationId";

    /// <summary>The correlation id set by the correlation middleware, falling back to the ASP.NET trace identifier.</summary>
    public static string GetCorrelationId(this HttpContext context) =>
        context.Items.TryGetValue(CorrelationIdItemKey, out var value) && value is string id ? id : context.TraceIdentifier;
}
