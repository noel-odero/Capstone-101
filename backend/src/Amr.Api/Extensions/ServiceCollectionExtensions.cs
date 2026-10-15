using Amr.Api.Configuration;
using Amr.Api.Errors;
using Asp.Versioning;

namespace Amr.Api.Extensions;

public static class ServiceCollectionExtensions
{
    /// <summary>Controllers, JSON conventions, URL-segment API versioning and the problem-details contract.</summary>
    public static IServiceCollection AddAmrApi(this IServiceCollection services)
    {
        services
            .AddControllers()
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
