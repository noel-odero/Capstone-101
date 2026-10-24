using Amr.Api.Authentication;
using Amr.Api.Configuration;
using Amr.Api.Errors;
using Amr.Application.Interfaces.Services;
using Amr.Application.Services;
using Asp.Versioning;

namespace Amr.Api.Extensions;

public static class ServiceCollectionExtensions
{
    /// <summary>The API is the composition root, so it binds Application services to their interfaces.</summary>
    public static IServiceCollection AddAmrApplicationServices(this IServiceCollection services)
    {
        services.AddScoped<IHealthService, HealthService>();
        services.AddScoped<IModelInfoService, ModelInfoService>();
        services.AddScoped<IProfileValidationService, ProfileValidationService>();
        services.AddScoped<ISimulationService, SimulationService>();
        services.AddScoped<IComparisonService, ComparisonService>();
        services.AddScoped<IRecommendationService, RecommendationService>();
        services.AddScoped<IRunHistoryService, RunHistoryService>();
        services.AddScoped<IAnalysisComparisonService, AnalysisComparisonService>();
        services.AddScoped<IAnalysisCollectionService, AnalysisCollectionService>();
        services.AddScoped<ISampleService, SampleService>();
        return services;
    }

    /// <summary>Controllers, JSON conventions, URL-segment API versioning and the problem-details contract.</summary>
    public static IServiceCollection AddAmrApi(this IServiceCollection services)
    {
        services
            .AddControllers(options => options.Filters.Add<CsrfValidationFilter>())
            .AddJsonOptions(options => ApiJsonOptions.Configure(options.JsonSerializerOptions))
            .ConfigureApiBehaviorOptions(options => options.InvalidModelStateResponseFactory = AmrProblemDetails.FromModelState);

        services
            .AddApiVersioning(options =>
            {
                options.DefaultApiVersion = new ApiVersion(1, 0);
                options.AssumeDefaultVersionWhenUnspecified = false;
                options.ReportApiVersions = true;
                options.ApiVersionReader = new UrlSegmentApiVersionReader();
            })
            .AddMvc();

        services.AddProblemDetails(options =>
            options.CustomizeProblemDetails = context => AmrProblemDetails.Decorate(context.ProblemDetails, context.HttpContext));

        return services;
    }
}
