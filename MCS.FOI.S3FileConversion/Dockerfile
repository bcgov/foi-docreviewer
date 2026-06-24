FROM mcr.microsoft.com/dotnet/sdk:7.0 AS build-env
WORKDIR /app

COPY *.sln .
COPY MCS.FOI.S3FileConversion/*.csproj ./MCS.FOI.S3FileConversion/
COPY MCS.FOI.ExcelToPDF/*.csproj ./MCS.FOI.ExcelToPDF/
COPY MCS.FOI.PptToPDF/*.csproj ./MCS.FOI.PptToPDF/
COPY MCS.FOI.CalendarToPDF/*.csproj ./MCS.FOI.CalendarToPDF/
COPY MCS.FOI.MSGToPDF/*.csproj ./MCS.FOI.MSGToPDF/
COPY MCS.FOI.ExcelToPDFUnitTests/*.csproj ./MCS.FOI.ExcelToPDFUnitTests/
COPY MCS.FOI.EMLToPDF/*.csproj ./MCS.FOI.EMLToPDF/
COPY MCS.FOI.CalendarToPDFUnitTests/*.csproj ./MCS.FOI.CalendarToPDFUnitTests/
COPY MCS.FOI.MSGToPDFUnitTests/*.csproj ./MCS.FOI.MSGToPDFUnitTests/
COPY MCS.FOI.DocToPDFUnitTests/*.csproj ./MCS.FOI.DocToPDFUnitTests/
COPY MCS.FOI.DocToPDF/*.csproj ./MCS.FOI.DocToPDF/
COPY MCS.FOI.PPTToPDFUnitTests/*.csproj ./MCS.FOI.PPTToPDFUnitTests/

# COPY NuGet.Config /
# RUN ["cp", "/NuGet.Config", "/root/.nuget/NuGet/NuGet.Config"]

# Restore as distinct layers
RUN dotnet restore

# Copy everything else
COPY MCS.FOI.S3FileConversion/. ./MCS.FOI.S3FileConversion/
COPY MCS.FOI.ExcelToPDF/. ./MCS.FOI.ExcelToPDF/
COPY MCS.FOI.PptToPDF/. ./MCS.FOI.PptToPDF/
COPY MCS.FOI.CalendarToPDF/. ./MCS.FOI.CalendarToPDF/
COPY MCS.FOI.MSGToPDF/. ./MCS.FOI.MSGToPDF/
COPY MCS.FOI.DocToPDF/. ./MCS.FOI.DocToPDF/
COPY MCS.FOI.EMLToPDF/. ./MCS.FOI.EMLToPDF/

WORKDIR /app/MCS.FOI.S3FileConversion

# Build and publish a release
RUN dotnet publish -c Release -o out


# Build runtime image
FROM mcr.microsoft.com/dotnet/runtime:7.0
WORKDIR /app

# fonts
# COPY ["Fonts/*.*", "/usr/local/share/fonts/"]
# either copy fonts to font folder in project path, or run following command in cmd
# docker cp C:/Windows/Fonts/. ** docker image hash code **:/usr/local/share/fonts
RUN apt-get update && apt-get install -y curl unzip
RUN curl -o fonts.zip "https://citz-foi-prod.objectstore.gov.bc.ca/records-upload-formats/fonts.zip"  \
&& unzip fonts.zip -d /usr/local/share/fonts \
&& rm fonts.zip

RUN apt-get update && apt-get install -y libfontconfig1 xvfb
# RUN echo "deb http://httpredir.debian.org/debian buster main contrib non-free" > /etc/apt/sources.list \ 
#     && echo "deb http://httpredir.debian.org/debian buster-updates main contrib non- free" >> /etc/apt/sources.list \
#     && echo "deb http://security.debian.org/ buster/updates main contrib non-free" >> /etc/apt/sources.list \
#     && echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections \
#     && apt-get update \
#     && apt-get install -y \
#         fonts-arphic-ukai \
#         fonts-arphic-uming \
#         fonts-ipafont-mincho \
#         fonts-ipafont-gothic \
#         fonts-unfonts-core \
#         ttf-wqy-zenhei \
#         ttf-mscorefonts-installer \
#     && apt-get clean \
#     && apt-get autoremove -y \
#     && rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
     apt-get install -yq --no-install-recommends \ 
     libasound2 libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 \ 
     libexpat1 libfontconfig1 libgcc1 libgconf-2-4 libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 \ 
     libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 \ 
     libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 \ 
     libnss3 libgbm1 libgdiplus \
     libx11-dev libx11-xcb-dev libxcb-icccm4-dev libxcb-image0-dev libxcb-keysyms1-dev libxcb-randr0-dev libxcb-render-util0-dev libxcb-render0-dev libxcb-shm0-dev libxcb-util0-dev libxcb-xfixes0-dev libxcb-xkb-dev libxcb1-dev libxfixes-dev libxrandr-dev libxrender-dev
COPY --from=build-env /app/MCS.FOI.S3FileConversion/out ./
RUN chmod a+rwx -R /app
#RUN chmod a+rwx -R /vault/secrets/conversion
ENTRYPOINT ["dotnet", "MCS.FOI.S3FileConversion.dll"]
