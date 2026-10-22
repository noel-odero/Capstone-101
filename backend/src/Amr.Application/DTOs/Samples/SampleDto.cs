using System.ComponentModel.DataAnnotations;
using Amr.Application.Validators;

namespace Amr.Application.DTOs.Samples;

public sealed record CreateSampleRequest
{
    [Required, StringLength(80, MinimumLength = 1)]
    public required string Label { get; init; }

    [Required, ResistanceProfile]
    public required IReadOnlyList<int> ResistanceProfile { get; init; }
}

public sealed record SampleRunDto(Guid Id, DateTimeOffset CreatedAtUtc);

public sealed record SampleDto(Guid Id, string Label, DateTimeOffset AddedAtUtc, IReadOnlyList<int> ResistanceProfile, IReadOnlyList<SampleRunDto> Runs);
