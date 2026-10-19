namespace Amr.Application.Interfaces.Identity;

/// <summary>
/// The authenticated caller of the current request. Stored runs belong to the user who created them, and the
/// repository scopes every read and write to this id. It is never taken from a request body or a client-supplied header.
/// </summary>
public interface ICurrentUser
{
    /// <summary>The signed-in user's id (a GUID in text form); null when the request is anonymous.</summary>
    string? UserId { get; }
}
