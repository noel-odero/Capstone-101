using Amr.Application.Interfaces.Identity;

namespace Amr.TestSupport;

/// <summary>A fixed caller for tests that exercise storage below the HTTP layer; null models an anonymous request.</summary>
public sealed class FixedCurrentUser(string? userId) : ICurrentUser
{
    public string? UserId { get; } = userId;
}
