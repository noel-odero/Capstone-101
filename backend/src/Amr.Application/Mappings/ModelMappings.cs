using Amr.Application.DTOs.Antibiotics;
using Amr.Application.DTOs.Common;
using Amr.Application.DTOs.Model;
using Amr.Application.PythonContracts;

namespace Amr.Application.Mappings;

/// <summary>Public model contract. Internal manifest paths, the inference device and the manifest hash are not exposed.</summary>
public static class ModelMappings
{
    public static ModelInfoDto ToDto(this PythonModelInfo model) => new(
        model.ManifestVersion,
        model.ModelId,
        model.Algorithm,
        model.CheckpointSha256,
        model.InteractionDataSha256,
        model.ScenarioId,
        model.Horizon,
        model.AntibioticOrder,
        new ObservationLayoutDto(model.Observation.Shape, model.Observation.Dtype, model.Observation.Layout, model.Observation.ResistanceEncoding),
        new ActionSpaceDto(model.ActionSpace.Type, model.ActionSpace.N),
        model.ActionMasking.Rule,
        model.Inference.Deterministic,
        model.TransitionStatusDefinitions,
        model.ServiceVersion,
        model.Disclaimer)
    {
        Policies = model.Policies?.ToDictionary(pair => pair.Key,
            pair => new PolicyModelDto(pair.Value.ModelId, pair.Value.Algorithm, pair.Value.CheckpointSha256)),
    };

    public static AntibioticCatalogueDto ToDto(this PythonAntibiotics catalogue) => new(
        catalogue.Antibiotics.Select(item => new AntibioticDto(item.ActionId, item.Name, item.DrugClass)).ToList(),
        catalogue.ResistanceEncoding);
}
