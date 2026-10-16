namespace Amr.Application.DTOs.Antibiotics;

public sealed record AntibioticDto(int ActionId, string Name, string? DrugClass);

/// <summary>Antibiotics in canonical action order, as reported by the Python service.</summary>
public sealed record AntibioticCatalogueDto(
    IReadOnlyList<AntibioticDto> Antibiotics,
    IReadOnlyDictionary<string, int> ResistanceEncoding);
