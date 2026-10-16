using System.Text.Json;
using System.Text.Json.Serialization;

namespace Amr.Infrastructure.Persistence;

/// <summary>JSON stored in jsonb columns (state snapshots, candidates, metric definitions, the comparison contract). Strict, camelCase, enums as snake_case strings.</summary>
internal static class PersistenceJson
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        NumberHandling = JsonNumberHandling.Strict,
        RespectNullableAnnotations = true,
        RespectRequiredConstructorParameters = true,
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.SnakeCaseLower, allowIntegerValues: false) },
    };

    public static string Serialize<T>(T value) => JsonSerializer.Serialize(value, Options);

    public static T Deserialize<T>(string json) =>
        JsonSerializer.Deserialize<T>(json, Options) ?? throw new JsonException("A stored JSON column was null.");
}
