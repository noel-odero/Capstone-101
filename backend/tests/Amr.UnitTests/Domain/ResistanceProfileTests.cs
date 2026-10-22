using Amr.Domain.ValueObjects;

namespace Amr.UnitTests.Domain;

public class ResistanceProfileTests
{
    [Theory]
    [InlineData(new int[] { 0, 0, 0, 0, 0, 0, 0 })]
    [InlineData(new int[] { 1, 1, 1, 1, 1, 1, 1 })]
    [InlineData(new int[] { 1, 0, 1, 0, 0, 1, 0 })]
    public void Validate_accepts_seven_binary_values(int[] values)
    {
        Assert.Null(ResistanceProfile.Validate(values));
    }

    [Theory]
    [InlineData(new int[] { })]
    [InlineData(new int[] { 0, 0, 0, 0, 0, 0 })]
    [InlineData(new int[] { 0, 0, 0, 0, 0, 0, 0, 0 })]
    [InlineData(new int[] { 0, 0, 0, 0, 0, 0, 2 })]
    [InlineData(new int[] { -1, 0, 0, 0, 0, 0, 0 })]
    public void Validate_rejects_wrong_length_and_non_binary_values(int[] values)
    {
        Assert.NotNull(ResistanceProfile.Validate(values));
    }

    [Fact]
    public void Validate_rejects_null()
    {
        Assert.NotNull(ResistanceProfile.Validate(null));
    }
}
