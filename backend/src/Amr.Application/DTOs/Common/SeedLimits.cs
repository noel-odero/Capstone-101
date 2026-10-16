namespace Amr.Application.DTOs.Common;

/// <summary>Seed range accepted by the Python service (unsigned 32-bit).</summary>
public static class SeedLimits
{
    public const long Min = 0;
    public const long Max = uint.MaxValue;
}
