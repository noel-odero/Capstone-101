using Amr.Domain.Exceptions;

namespace Amr.Domain.ValueObjects;

/// <summary>Representation of a binary resistance profile in the canonical antibiotic order (0 susceptible, 1 resistant). Carries no scientific rules.</summary>
public sealed class ResistanceProfile
{
    public const int Length = 7;
    public const int Susceptible = 0;
    public const int Resistant = 1;

    private ResistanceProfile(int[] values) => Values = Array.AsReadOnly(values);

    public IReadOnlyList<int> Values { get; }

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

    public static ResistanceProfile Create(IReadOnlyList<int>? values)
    {
        var error = Validate(values);
        return error is null ? new ResistanceProfile([.. values!]) : throw new DomainValidationException(error);
    }

    public string ToLabel() => string.Concat(Values.Select(value => value == Resistant ? 'R' : 'S'));
}
