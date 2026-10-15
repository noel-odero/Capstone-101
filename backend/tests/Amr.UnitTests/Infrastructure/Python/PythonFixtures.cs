using System.Net;
using System.Text;
using System.Text.Json.Nodes;

namespace Amr.UnitTests.Infrastructure.Python;

/// <summary>Real responses captured from the Python service; see Fixtures/generate_python_fixtures.py.</summary>
internal static class PythonFixtures
{
    public static string Read(string name) =>
        File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Fixtures", "python", $"{name}.json"));

    public static string Mutate(string name, Action<JsonNode> change)
    {
        var node = JsonNode.Parse(Read(name))!;
        change(node);
        return node.ToJsonString();
    }

    public static HttpResponseMessage Respond(HttpStatusCode status, string body, string mediaType = "application/json") =>
        new(status) { Content = new StringContent(body, Encoding.UTF8, mediaType) };

    public static HttpResponseMessage Fixture(string name, HttpStatusCode status = HttpStatusCode.OK) => Respond(status, Read(name));
}
