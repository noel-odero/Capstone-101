using Amr.Api.Extensions;
using Amr.Infrastructure.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddAmrApi();
builder.Services.AddAmrApplicationServices();
builder.Services.AddInfrastructure(builder.Configuration);

var app = builder.Build();

app.UseAmrMiddleware();
app.MapControllers();

app.Run();

public partial class Program;
