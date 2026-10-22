using System.Security.Claims;
using Amr.Application.Interfaces.Identity;

namespace Amr.Api.Authentication;

/// <summary>The caller's stable id, read from the validated principal. Nothing in the request body or headers can set it.</summary>
public sealed class HttpContextCurrentUser(IHttpContextAccessor accessor) : ICurrentUser
{
    public string? UserId
    {
        get
        {
            var user = accessor.HttpContext?.User;
            return user?.Identity?.IsAuthenticated == true ? user.FindFirstValue(ClaimTypes.NameIdentifier) : null;
        }
    }
}
