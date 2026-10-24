using Amr.Api.Routing;
using Amr.Application.DTOs.Analyses;
using Amr.Application.Interfaces.Services;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

[Route(ApiRoutes.Base + "/analysis-collections")]
public sealed class AnalysisCollectionsController(IAnalysisCollectionService collections) : ApiControllerBase
{
    [HttpGet]
    public Task<IReadOnlyList<AnalysisCollectionDto>> List(CancellationToken cancellationToken) => collections.ListAsync(cancellationToken);

    [HttpPost]
    public async Task<ActionResult<AnalysisCollectionDto>> Create(CreateAnalysisCollectionRequest request, CancellationToken cancellationToken) =>
        StatusCode(StatusCodes.Status201Created, await collections.CreateAsync(request, cancellationToken));
}
