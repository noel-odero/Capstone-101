using System.Text.Json;
using System.Text.Json.Serialization;

namespace Amr.Infrastructure.Python;

/// <summary>
/// Wire format of the Python service: snake_case, strict numbers, and a missing or null non-nullable member is an
/// error so a changed contract surfaces as an invalid response instead of a silently defaulted value.
/// Unknown members are ignored; dictionary keys keep their Python spelling.
/// </summary>
internal static class PythonJson
{
    public static readonly JsonSerializerOptions Options = new(JsonSerializerDefaults.General)
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        NumberHandling = JsonNumberHandling.Strict,
        RespectNullableAnnotations = true,
        RespectRequiredConstructorParameters = true,
    };
}
