using Amr.Domain.Exceptions;
using Amr.Domain.ValueObjects;

namespace Amr.UnitTests.Domain;

public class ResistanceProfileTests
{
    [Theory]
    [InlineData(new int[] { 0, 0, 0, 0, 0, 0, 0 })]
    [InlineData(new int[] { 1, 1, 1, 1, 1, 1, 1 })]
    [InlineData(new int[] { 1, 0, 1, 0, 0, 1, 0 })]
    public void Create_accepts_seven_binary_values(int[] values)
    {
        var profile = ResistanceProfile.Create(values);

        Assert.Equal(values, profile.Values);
    }

    [Theory]
    [InlineData(new int[] { })]
    [InlineData(new int[] { 0, 0, 0, 0, 0, 0 })]
    [InlineData(new int[] { 0, 0, 0, 0, 0, 0, 0, 0 })]
    [InlineData(new int[] { 0, 0, 0, 0, 0, 0, 2 })]
    [InlineData(new int[] { -1, 0, 0, 0, 0, 0, 0 })]
    public void Create_rejects_wrong_length_and_non_binary_values(int[] values)
    {
        Assert.NotNull(ResistanceProfile.Validate(values));
        Assert.Throws<DomainValidationException>(() => ResistanceProfile.Create(values));
    }

    [Fact]
    public void Validate_rejects_null()
    {
        Assert.NotNull(ResistanceProfile.Validate(null));
    }

    [Fact]
    public void Values_are_a_copy_that_later_changes_to_the_input_cannot_affect()
    {
        var input = new[] { 0, 1, 0, 0, 0, 0, 0 };
        var profile = ResistanceProfile.Create(input);

        input[0] = 1;

        Assert.Equal(0, profile.Values[0]);
    }

    [Fact]
    public void ToLabel_uses_S_for_susceptible_and_R_for_resistant_in_order()
    {
        Assert.Equal("RSRSSRS", ResistanceProfile.Create([1, 0, 1, 0, 0, 1, 0]).ToLabel());
    }
}
