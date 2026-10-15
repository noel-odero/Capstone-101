namespace Amr.Application.DTOs.Health;

public enum HealthState
{
    Healthy,
    Degraded,
    Unhealthy,
}

public static class HealthComponents
{
    public const string Api = "api";
    public const string Database = "database";
    public const string PythonService = "pythonService";
    public const string Model = "model";
}

/// <param name="Detail">A stable error code when the component is not healthy; never infrastructure details.</param>
public sealed record ComponentHealthDto(string Name, HealthState Status, string? Detail);

/// <param name="Ready">True only when every component required to serve runs is healthy, including a verified model.</param>
public sealed record HealthDto(HealthState Status, bool Ready, IReadOnlyList<ComponentHealthDto> Components);
