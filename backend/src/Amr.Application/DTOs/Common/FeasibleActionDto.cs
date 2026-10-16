namespace Amr.Application.DTOs.Common;

/// <summary>An action the simulator allows (the antibiotic is susceptible). It is not a clinical recommendation.</summary>
/// <param name="HasCandidateTransition">False means unsupported_no_candidate: the simulator has no modeled outcome and leaves the profile unchanged.</param>
public sealed record FeasibleActionDto(int ActionId, string Antibiotic, bool HasCandidateTransition);
