using Amr.Api.Authentication;
using Amr.Api.Extensions;
using Amr.Infrastructure.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddAmrApi();
builder.Services.AddDeploymentHosting(builder.Configuration);
builder.Services.AddAmrAuthentication(builder.Configuration, builder.Environment);
builder.Services.AddAmrApplicationServices();
builder.Services.AddInfrastructure(builder.Configuration);

var app = builder.Build();

app.UseForwardedHeaders();
app.UseAmrMiddleware();
app.UseAuthentication();
app.UseAuthorization();
app.UseRateLimiter();
app.MapControllers();

app.Run();

public partial class Program;
