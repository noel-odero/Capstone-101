FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /source/backend
COPY backend/ ./
RUN dotnet restore src/Amr.Api/Amr.Api.csproj --locked-mode
RUN dotnet publish src/Amr.Api/Amr.Api.csproj -c Release --no-restore -o /out/api
RUN dotnet tool restore
RUN ConnectionStrings__Amr="Host=postgres;Database=amr;Username=amr;Password=build-only" \
    dotnet tool run dotnet-ef migrations bundle --project src/Amr.Infrastructure \
    --startup-project src/Amr.Api --configuration Release --no-build --output /out/efbundle

FROM mcr.microsoft.com/dotnet/aspnet:10.0
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/lib/amr/keys && chown app:app /var/lib/amr/keys
WORKDIR /app
COPY --from=build /out/api/ ./
COPY --from=build /out/efbundle ./efbundle
ENV ASPNETCORE_HTTP_PORTS=8080
USER app
EXPOSE 8080
ENTRYPOINT ["dotnet", "Amr.Api.dll"]
