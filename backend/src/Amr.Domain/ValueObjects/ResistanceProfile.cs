namespace Amr.Domain.ValueObjects;

/// <summary>Validates binary resistance values in the canonical antibiotic order.</summary>
public static class ResistanceProfile
{
    public const int Length = 7;
    public const int Susceptible = 0;
    public const int Resistant = 1;

    /// <summary>Returns a description of the first violation, or null when the values form a valid profile.</summary>
    public static string? Validate(IReadOnlyList<int>? values)
    {
        if (values is null)
        {
            return "A resistance profile is required.";
        }

        if (values.Count != Length)
        {
            return $"A resistance profile must have exactly {Length} values.";
        }

        return values.Any(value => value is not (Susceptible or Resistant))
            ? $"Resistance values must be {Susceptible} (susceptible) or {Resistant} (resistant)."
            : null;
    }
}
