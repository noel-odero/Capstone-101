using Amr.Application.DTOs.Common;

namespace Amr.Application.Services;

/// <summary>Cheap integrity checks that a Python run answers the request that was sent. They compare values; they compute nothing scientific.</summary>
internal static class RunResponseChecks
{
    public static bool Answers(RunRequestBase request, IReadOnlyList<int> initialProfile, long environmentSeed) =>
        request.ResistanceProfile.SequenceEqual(initialProfile)
        && (request.EnvironmentSeed is null || request.EnvironmentSeed == environmentSeed);
}
