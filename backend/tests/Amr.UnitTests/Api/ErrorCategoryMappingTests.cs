using Amr.Api.Errors;
using Amr.Application.Errors;

namespace Amr.UnitTests.Api;

public class ErrorCategoryMappingTests
{
    public static TheoryData<ErrorCategory, int> ExpectedStatuses => new()
    {
        { ErrorCategory.InvalidRequest, 422 },
        { ErrorCategory.NotFound, 404 },
        { ErrorCategory.DependencyUnavailable, 503 },
        { ErrorCategory.UpstreamFailure, 502 },
        { ErrorCategory.NotImplemented, 501 },
        { ErrorCategory.Internal, 500 },
    };

    [Theory]
    [MemberData(nameof(ExpectedStatuses))]
    public void Each_category_maps_to_its_documented_status(ErrorCategory category, int status)
    {
        Assert.Equal(status, AmrProblemDetails.StatusFor(category));
    }

    [Fact]
    public void Every_category_has_a_mapping()
    {
        Assert.Equal(
            Enum.GetValues<ErrorCategory>().Order(),
            ExpectedStatuses.Select(row => (ErrorCategory)row[0]).Order());
    }

    [Fact]
    public void An_unmapped_category_fails_loudly()
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => AmrProblemDetails.StatusFor((ErrorCategory)99));
    }
}
