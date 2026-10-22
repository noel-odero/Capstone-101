using Amr.Api.Routing;
using Amr.Application.DTOs.Samples;
using Amr.Application.Interfaces.Persistence;
using Microsoft.AspNetCore.Mvc;

namespace Amr.Api.Controllers;

[Route(ApiRoutes.Base + "/samples")]
public sealed class SamplesController(ISampleRepository samples) : ApiControllerBase
{
    [HttpGet]
    public async Task<ActionResult<IReadOnlyList<SampleDto>>> List(CancellationToken cancellationToken) =>
        Ok(await samples.ListAsync(cancellationToken));

    [HttpGet("{id:guid}")]
    public async Task<ActionResult<SampleDto>> Get(Guid id, CancellationToken cancellationToken)
    {
        var sample = await samples.FindAsync(id, cancellationToken);
        return sample is null ? NotFoundProblem("sample_not_found", "No sample has this id.") : sample;
    }

    [HttpPost]
    public async Task<ActionResult<SampleDto>> Create(CreateSampleRequest request, CancellationToken cancellationToken)
    {
        var sample = await samples.CreateAsync(request, cancellationToken);
        return CreatedAtAction(nameof(Get), new { id = sample.Id, version = ApiRoutes.UrlVersion1 }, sample);
    }
}
