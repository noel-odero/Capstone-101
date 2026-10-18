using System.Collections.Concurrent;
using Microsoft.Extensions.Logging;

namespace Amr.IntegrationTests.Infrastructure;

public sealed record CapturedLog(string Category, LogLevel Level, string Message, Exception? Exception, IReadOnlyList<object?> Scopes)
{
    public string? CorrelationId => Scopes
        .OfType<IEnumerable<KeyValuePair<string, object>>>()
        .SelectMany(scope => scope)
        .Where(pair => pair.Key == "CorrelationId")
        .Select(pair => pair.Value as string)
        .FirstOrDefault();
}

public sealed class CapturingLoggerProvider : ILoggerProvider, ISupportExternalScope
{
    private IExternalScopeProvider _scopes = new LoggerExternalScopeProvider();

    public ConcurrentQueue<CapturedLog> Entries { get; } = new();

    public ILogger CreateLogger(string categoryName) => new CapturingLogger(this, categoryName);

    public void SetScopeProvider(IExternalScopeProvider scopeProvider) => _scopes = scopeProvider;

    public void Dispose()
    {
    }

    private sealed class CapturingLogger(CapturingLoggerProvider provider, string category) : ILogger
    {
        public IDisposable? BeginScope<TState>(TState state)
            where TState : notnull => provider._scopes.Push(state);

        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
        {
            var scopes = new List<object?>();
            provider._scopes.ForEachScope((scope, list) => list.Add(scope), scopes);
            provider.Entries.Enqueue(new CapturedLog(category, logLevel, formatter(state, exception), exception, scopes));
        }
    }
}
