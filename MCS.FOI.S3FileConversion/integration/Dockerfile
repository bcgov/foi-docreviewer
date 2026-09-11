FROM mcr.microsoft.com/dotnet/sdk:10.0-noble AS build
WORKDIR /src

COPY MCS.FOI.S3FileConversionIntegrationTests/MCS.FOI.S3FileConversionIntegrationTests.csproj MCS.FOI.S3FileConversionIntegrationTests/
COPY MCS.FOI.S3FileConversion/MCS.FOI.S3FileConversion.csproj MCS.FOI.S3FileConversion/
COPY MCS.FOI.ExcelToPDF/MCS.FOI.ExcelToPDF.csproj MCS.FOI.ExcelToPDF/
COPY MCS.FOI.PptToPDF/MCS.FOI.PPTToPDF.csproj MCS.FOI.PptToPDF/
COPY MCS.FOI.CalendarToPDF/MCS.FOI.CalendarToPDF.csproj MCS.FOI.CalendarToPDF/
COPY MCS.FOI.MSGToPDF/MCS.FOI.MSGToPDF.csproj MCS.FOI.MSGToPDF/
COPY MCS.FOI.DocToPDF/MCS.FOI.DocToPDF.csproj MCS.FOI.DocToPDF/
RUN dotnet restore MCS.FOI.S3FileConversionIntegrationTests/MCS.FOI.S3FileConversionIntegrationTests.csproj

COPY MCS.FOI.S3FileConversionIntegrationTests/*.cs MCS.FOI.S3FileConversionIntegrationTests/
COPY MCS.FOI.S3FileConversion/. MCS.FOI.S3FileConversion/
COPY MCS.FOI.ExcelToPDF/. MCS.FOI.ExcelToPDF/
COPY MCS.FOI.PptToPDF/. MCS.FOI.PptToPDF/
COPY MCS.FOI.CalendarToPDF/. MCS.FOI.CalendarToPDF/
COPY MCS.FOI.MSGToPDF/. MCS.FOI.MSGToPDF/
COPY MCS.FOI.DocToPDF/. MCS.FOI.DocToPDF/
COPY MCS.FOI.DocToPDFUnitTests/SourceFiles/simple-test-doc.docx MCS.FOI.DocToPDFUnitTests/SourceFiles/simple-test-doc.docx
COPY MCS.FOI.MSGToPDFUnitTests/SourceFiles/Test-MSG-File-with-Attachments.msg MCS.FOI.MSGToPDFUnitTests/SourceFiles/Test-MSG-File-with-Attachments.msg
RUN dotnet build \
    MCS.FOI.S3FileConversionIntegrationTests/MCS.FOI.S3FileConversionIntegrationTests.csproj \
    --configuration Release

FROM mcr.microsoft.com/dotnet/sdk:10.0-noble
WORKDIR /tests
COPY --from=build /src/MCS.FOI.S3FileConversionIntegrationTests/ ./
ENTRYPOINT ["dotnet", "test", "--no-build", "--configuration", "Release", "--logger", "trx;LogFileName=conversion-integration.trx", "--results-directory", "/test-results"]
