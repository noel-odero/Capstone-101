using Amr.Application.DTOs.Common;

namespace Amr.Application.DTOs.Comparisons;

public sealed record CreateComparisonRequest : RunRequestBase
{
    public Guid? SampleId { get; init; }
}
