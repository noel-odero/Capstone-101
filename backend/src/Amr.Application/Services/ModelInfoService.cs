using Amr.Application.DTOs.Antibiotics;
using Amr.Application.DTOs.Model;
using Amr.Application.Interfaces.Clients;
using Amr.Application.Interfaces.Services;
using Amr.Application.Mappings;

namespace Amr.Application.Services;

public sealed class ModelInfoService(IPythonServiceClient python) : IModelInfoService
{
    public async Task<ModelInfoDto> GetModelAsync(CancellationToken cancellationToken) =>
        (await python.GetModelAsync(cancellationToken)).ToDto();

    public async Task<AntibioticCatalogueDto> GetAntibioticsAsync(CancellationToken cancellationToken) =>
        (await python.GetAntibioticsAsync(cancellationToken)).ToDto();
}
