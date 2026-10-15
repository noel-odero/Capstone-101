using Amr.Infrastructure.Python;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;

namespace Amr.UnitTests.Infrastructure.Python;

/// <summary>Scriptable HTTP handler that records every request, so tests can assert what was sent and how often.</summary>
internal sealed class StubHandler(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> respond) : HttpMessageHandler
{
    public List<RecordedRequest> Requests { get; } = [];

    public int CallCount => Requests.Count;

    public static StubHandler Returning(Func<HttpResponseMessage> response) => new((_, _) => Task.FromResult(response()));

    public static StubHandler Throwing(Exception exception) => new((_, _) => throw exception);

    public static StubHandler Hanging() => new(async (_, token) =>
    {
        await Task.Delay(Timeout.Infinite, token);
        return new HttpResponseMessage();
    });

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        var body = request.Content is null ? null : await request.Content.ReadAsStringAsync(cancellationToken);
        Requests.Add(new RecordedRequest(request.Method, request.RequestUri!, body, request.Headers.Accept.ToString(), cancellationToken));
        return await respond(request, cancellationToken);
    }
}

internal sealed record RecordedRequest(HttpMethod Method, Uri Uri, string? Body, string Accept, CancellationToken Token);

internal static class ClientFactory
{
    public static PythonServiceClient Create(StubHandler handler, int requestTimeoutSeconds = 60, int healthTimeoutSeconds = 3)
    {
        var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("http://python.test/"),
            Timeout = Timeout.InfiniteTimeSpan,
        };
        var options = Options.Create(new PythonServiceOptions
        {
            BaseUrl = new Uri("http://python.test/"),
            RequestTimeoutSeconds = requestTimeoutSeconds,
            HealthTimeoutSeconds = healthTimeoutSeconds,
        });
        return new PythonServiceClient(httpClient, options, new PythonServiceErrorMapper(NullLogger<PythonServiceErrorMapper>.Instance));
    }
}
