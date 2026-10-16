using System.Text.Json;
using System.Text.Json.Serialization;

namespace Amr.Api.Configuration;

public static class ApiJsonOptions
{
    /// <summary>camelCase properties; enums as snake_case strings (for example "random_susceptible_baseline"); numeric enum values, numbers written as strings and unknown members are rejected.</summary>
    public static void Configure(JsonSerializerOptions options)
    {
        options.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
        options.NumberHandling = JsonNumberHandling.Strict;
        options.UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow;
        options.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.SnakeCaseLower, allowIntegerValues: false));
    }
}
