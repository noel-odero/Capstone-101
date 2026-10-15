using System.ComponentModel.DataAnnotations;
using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Comparisons;
using Amr.Application.DTOs.Profiles;
using Amr.Application.DTOs.Simulations;
using Amr.Domain.Enums;

namespace Amr.UnitTests.Application;

public class RequestValidationTests
{
    private static readonly int[] ValidProfile = [0, 1, 0, 0, 0, 0, 0];

    public static TheoryData<int[]> MalformedProfiles => new()
    {
        { [] },
        { [0, 0, 0, 0, 0, 0] },
        { [0, 0, 0, 0, 0, 0, 0, 0] },
        { [0, 0, 0, 0, 0, 0, 2] },
        { [-1, 0, 0, 0, 0, 0, 0] },
    };

    private static List<ValidationResult> Validate(object instance)
    {
        var results = new List<ValidationResult>();
        Validator.TryValidateObject(instance, new ValidationContext(instance), results, validateAllProperties: true);
        return results;
    }

    private static CreateSimulationRequest Simulation(int[]? profile = null, long? environmentSeed = null, long? policySeed = null, StrategyKind strategy = StrategyKind.Ppo) =>
        new() { ResistanceProfile = profile ?? ValidProfile, Strategy = strategy, EnvironmentSeed = environmentSeed, PolicySeed = policySeed };

    [Fact]
    public void Valid_requests_pass()
    {
        Assert.Empty(Validate(new ValidateProfileRequest { ResistanceProfile = ValidProfile }));
        Assert.Empty(Validate(Simulation(environmentSeed: 0, policySeed: SeedLimits.Max)));
        Assert.Empty(Validate(new CreateComparisonRequest { ResistanceProfile = ValidProfile, EnvironmentSeed = 100001, PolicySeed = 900001 }));
    }

    [Theory]
    [MemberData(nameof(MalformedProfiles))]
    public void Malformed_profiles_are_rejected_by_every_request_that_carries_one(int[] profile)
    {
        var results = new[]
        {
            Validate(new ValidateProfileRequest { ResistanceProfile = profile }),
            Validate(Simulation(profile)),
            Validate(new CreateComparisonRequest { ResistanceProfile = profile }),
        };

        Assert.All(results, errors => Assert.Contains(errors, error => error.MemberNames.Contains(nameof(ValidateProfileRequest.ResistanceProfile))));
    }

    [Theory]
    [InlineData(-1L)]
    [InlineData(SeedLimits.Max + 1)]
    public void Seeds_outside_the_unsigned_32_bit_range_are_rejected(long seed)
    {
        Assert.Contains(Validate(Simulation(environmentSeed: seed)), error => error.MemberNames.Contains(nameof(RunRequestBase.EnvironmentSeed)));
        Assert.Contains(Validate(Simulation(policySeed: seed)), error => error.MemberNames.Contains(nameof(RunRequestBase.PolicySeed)));
        Assert.NotEmpty(Validate(new CreateComparisonRequest { ResistanceProfile = ValidProfile, EnvironmentSeed = seed }));
    }

    [Fact]
    public void An_undefined_strategy_value_is_rejected()
    {
        Assert.Contains(Validate(Simulation(strategy: (StrategyKind)99)), error => error.MemberNames.Contains(nameof(CreateSimulationRequest.Strategy)));
    }

    [Fact]
    public void Recent_runs_query_defaults_are_within_limits()
    {
        var query = new RecentRunsQuery();

        Assert.Equal((1, PaginationLimits.DefaultPageSize), (query.Page, query.PageSize));
        Assert.Empty(Validate(query));
    }

    [Theory]
    [InlineData(0, 10)]
    [InlineData(-3, 10)]
    [InlineData(1, 0)]
    [InlineData(1, PaginationLimits.MaxPageSize + 1)]
    public void Recent_runs_query_rejects_non_positive_pages_and_oversized_page_sizes(int page, int pageSize)
    {
        Assert.NotEmpty(Validate(new RecentRunsQuery { Page = page, PageSize = pageSize }));
    }

    [Fact]
    public void Recent_runs_query_accepts_the_maximum_page_size()
    {
        Assert.Empty(Validate(new RecentRunsQuery { Page = 1, PageSize = PaginationLimits.MaxPageSize }));
    }
}
