using System.Net;
using Amr.Infrastructure.Python;
using Microsoft.Extensions.Logging;

namespace Amr.UnitTests.Infrastructure.Python;

public class PythonServiceErrorMapperLoggingTests
{
    private sealed class ListLogger<T> : ILogger<T>
    {
        public List<(LogLevel Level, string Message)> Entries { get; } = [];

        public IDisposable? BeginScope<TState>(TState state)
            where TState : notnull => null;

        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter) =>
            Entries.Add((logLevel, formatter(state, exception)));
    }

    [Fact]
    public void The_python_status_code_and_request_id_are_logged_for_support_but_not_returned()
    {
        var logger = new ListLogger<PythonServiceErrorMapper>();
        var mapper = new PythonServiceErrorMapper(logger);

        var error = mapper.FromResponse(HttpStatusCode.InternalServerError, PythonFixtures.Read("simulate_500_internal_error"));

        var logged = Assert.Single(logger.Entries);
        Assert.Equal(LogLevel.Warning, logged.Level);
        Assert.Contains("500", logged.Message, StringComparison.Ordinal);
        Assert.Contains("internal_error", logged.Message, StringComparison.Ordinal);
        Assert.Matches(@"python request [0-9a-f-]{36}", logged.Message);
        Assert.DoesNotContain("python request", error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void An_unrecognizable_response_is_logged_with_its_status_only()
    {
        var logger = new ListLogger<PythonServiceErrorMapper>();

        new PythonServiceErrorMapper(logger).FromResponse(HttpStatusCode.BadGateway, "<html>secret upstream page</html>");

        var logged = Assert.Single(logger.Entries);
        Assert.Contains("502", logged.Message, StringComparison.Ordinal);
        Assert.DoesNotContain("secret", logged.Message, StringComparison.Ordinal);
    }
}
