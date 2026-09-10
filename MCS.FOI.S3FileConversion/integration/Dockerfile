FROM mcr.microsoft.com/dotnet/sdk:10.0-noble AS build
WORKDIR /src

COPY MCS.FOI.S3FileConversionIntegrationTests/MCS.FOI.S3FileConversionIntegrationTests.csproj MCS.FOI.S3FileConversionIntegrationTests/
RUN dotnet restore MCS.FOI.S3FileConversionIntegrationTests/MCS.FOI.S3FileConversionIntegrationTests.csproj

COPY MCS.FOI.S3FileConversionIntegrationTests/*.cs MCS.FOI.S3FileConversionIntegrationTests/
COPY MCS.FOI.DocToPDFUnitTests/SourceFiles/simple-test-doc.docx MCS.FOI.DocToPDFUnitTests/SourceFiles/simple-test-doc.docx
RUN dotnet build MCS.FOI.S3FileConversionIntegrationTests/MCS.FOI.S3FileConversionIntegrationTests.csproj --configuration Release --no-restore

FROM mcr.microsoft.com/dotnet/sdk:10.0-noble
WORKDIR /tests
COPY --from=build /src/MCS.FOI.S3FileConversionIntegrationTests/ ./
ENTRYPOINT ["dotnet", "test", "--no-build", "--configuration", "Release", "--logger", "trx;LogFileName=docx-integration.trx", "--results-directory", "/test-results"]
