using System.ComponentModel.DataAnnotations;
using Amr.Domain.ValueObjects;

namespace Amr.Application.Validators;

/// <summary>Validates a binary resistance profile using the single rule in <see cref="ResistanceProfile"/>.</summary>
[AttributeUsage(AttributeTargets.Property | AttributeTargets.Parameter)]
public sealed class ResistanceProfileAttribute : ValidationAttribute
{
    protected override ValidationResult? IsValid(object? value, ValidationContext validationContext)
    {
        var error = ResistanceProfile.Validate(value as IReadOnlyList<int>);
        return error is null ? ValidationResult.Success : new ValidationResult(error, [validationContext.MemberName ?? string.Empty]);
    }
}
