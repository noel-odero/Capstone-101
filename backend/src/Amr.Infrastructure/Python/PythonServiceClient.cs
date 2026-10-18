using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Amr.Application.Interfaces.Clients;
using Amr.Application.PythonContracts;
using Microsoft.Extensions.Options;

namespace Amr.Infrastructure.Python;

/// <summary>
/// Typed HTTP client for the private Python service. Each call makes exactly one attempt: there are no automatic
/// retries, so a simulation or comparison can never be run twice by the client. Caller cancellation propagates as
/// OperationCanceledException; an elapsed request timeout becomes a python_service_timeout error.
/// </summary>
public sealed class PythonServiceClient(HttpClient httpClient, IOptions<PythonServiceOptions> options, PythonServiceErrorMapper errors)
    : IPythonServiceClient
{
    private readonly PythonServiceOptions _options = options.Value;

    public async Task<PythonHealth> GetHealthAsync(CancellationToken cancellationToken)
    {
        // A not-ready model is reported with 503 and the normal health body, so both statuses carry a PythonHealth.
        var (status, body) = await SendAsync(HttpMethod.Get, PythonEndpoints.Health, content: null, TimeSpan.FromSeconds(_options.HealthTimeoutSeconds), cancellationToken);
        return status is HttpStatusCode.OK or HttpStatusCode.ServiceUnavailable && TryDeserialize<PythonHealth>(body) is { } health
            ? health
            : throw errors.FromResponse(status, body);
    }

    public Task<PythonModelInfo> GetModelAsync(CancellationToken cancellationToken) =>
        RequestAsync<PythonModelInfo>(HttpMethod.Get, PythonEndpoints.Model, content: null, cancellationToken);

    public Task<PythonAntibiotics> GetAntibioticsAsync(CancellationToken cancellationToken) =>
        RequestAsync<PythonAntibiotics>(HttpMethod.Get, PythonEndpoints.Antibiotics, content: null, cancellationToken);

    public Task<PythonProfileValidation> ValidateProfileAsync(IReadOnlyList<int> resistanceProfile, CancellationToken cancellationToken) =>
        RequestAsync<PythonProfileValidation>(HttpMethod.Post, PythonEndpoints.ValidateProfile, new PythonProfileRequest(resistanceProfile), cancellationToken);

    public Task<PythonSimulation> SimulateAsync(PythonSimulateRequest request, CancellationToken cancellationToken) =>
        RequestAsync<PythonSimulation>(HttpMethod.Post, PythonEndpoints.Simulate, request, cancellationToken);

    public Task<PythonComparison> CompareAsync(PythonCompareRequest request, CancellationToken cancellationToken) =>
        RequestAsync<PythonComparison>(HttpMethod.Post, PythonEndpoints.Compare, request, cancellationToken);

    private async Task<T> RequestAsync<T>(HttpMethod method, string path, object? content, CancellationToken cancellationToken)
        where T : class
    {
        var (status, body) = await SendAsync(method, path, content, TimeSpan.FromSeconds(_options.RequestTimeoutSeconds), cancellationToken);
        if (status != HttpStatusCode.OK)
        {
            throw errors.FromResponse(status, body);
        }

        try
        {
            return JsonSerializer.Deserialize<T>(body, PythonJson.Options) ?? throw PythonServiceErrorMapper.InvalidResponse(innerException: null);
        }
        catch (JsonException exception)
        {
            throw PythonServiceErrorMapper.InvalidResponse(exception);
        }
    }

    private async Task<(HttpStatusCode Status, string Body)> SendAsync(
        HttpMethod method, string path, object? content, TimeSpan timeout, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        using var timeoutSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeoutSource.CancelAfter(timeout);

        try
        {
            using var request = new HttpRequestMessage(method, path);
            if (content is not null)
            {
                request.Content = JsonContent.Create(content, content.GetType(), mediaType: null, PythonJson.Options);
            }

            using var response = await httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, timeoutSource.Token);
            return (response.StatusCode, await response.Content.ReadAsStringAsync(timeoutSource.Token));
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            throw PythonServiceErrorMapper.Timeout();
        }
        catch (HttpRequestException exception)
        {
            throw PythonServiceErrorMapper.Unavailable(exception);
        }
    }

    private static T? TryDeserialize<T>(string body)
        where T : class
    {
        try
        {
            return JsonSerializer.Deserialize<T>(body, PythonJson.Options);
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
