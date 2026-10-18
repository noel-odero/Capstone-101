using Amr.Application.DTOs.Antibiotics;
using Amr.Application.DTOs.Model;

namespace Amr.Application.Interfaces.Services;

/// <summary>Read-only model identity and antibiotic catalogue, taken from the verified Python service.</summary>
public interface IModelInfoService
{
    Task<ModelInfoDto> GetModelAsync(CancellationToken cancellationToken);

    Task<AntibioticCatalogueDto> GetAntibioticsAsync(CancellationToken cancellationToken);
}
