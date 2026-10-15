using System.Net;
using System.Text;
using System.Text.Json;

namespace Amr.IntegrationTests.Infrastructure;

public static class HttpTestExtensions
{
    public static string Probe(string path) => $"/api/v1/stage-a-probe/{path}";

    public static Task<HttpResponseMessage> PostJsonAsync(this HttpClient client, string path, string json) =>
        client.PostAsync(path, new StringContent(json, Encoding.UTF8, "application/json"));

    public static async Task<JsonElement> ReadJsonAsync(this HttpResponseMessage response)
    {
        using var document = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync());
        return document.RootElement.Clone();
    }

    /// <summary>Asserts the RFC 9457 contract common to every error and returns the body.</summary>
    public static async Task<JsonElement> ReadProblemAsync(this HttpResponseMessage response, HttpStatusCode status, string code)
    {
        Assert.Equal(status, response.StatusCode);
        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);

        var problem = await response.ReadJsonAsync();
        Assert.Equal((int)status, problem.GetProperty("status").GetInt32());
        Assert.Equal(code, problem.GetProperty("code").GetString());
        Assert.Equal($"urn:amr:problem:{code}", problem.GetProperty("type").GetString());
        Assert.Equal(response.Headers.GetValues("X-Correlation-ID").Single(), problem.GetProperty("correlationId").GetString());
        return problem;
    }
}
