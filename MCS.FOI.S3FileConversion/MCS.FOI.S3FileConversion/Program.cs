using System.Text.Json;
using System.Text.Json.Nodes;
using MCS.FOI.S3FileConversion.Messaging;
using MCS.FOI.S3FileConversion.Utilities;
using Microsoft.Extensions.Configuration;
using Serilog;
using StackExchange.Redis;

namespace MCS.FOI.S3FileConversion;

internal static class Program
{
    private static async Task Main(string[] args)
    {
        try
        {
            var configuration = new ConfigurationBuilder()
                .AddJsonFile("appsettings.json", optional: true, reloadOnChange: true)
                .AddEnvironmentVariables()
                .Build();

            Log.Logger = new LoggerConfiguration()
                .ReadFrom.Configuration(configuration)
                .CreateLogger();

            Log.Information("MCS FOI S3FileConversion Service is up");
            LoadConversionSettings(configuration);

            using var client = new HttpClient();
            var response = await client.GetAsync(
                Environment.GetEnvironmentVariable("RECORD_FORMATS"));
            response.EnsureSuccessStatusCode();
            var responseBody = await response.Content.ReadAsStringAsync();
            var formats = JsonSerializer.Deserialize<JsonNode>(responseBody)!;

            ConversionSettings.ConversionFormats = formats["conversion"]!
                .AsArray()
                .Select(format => format!.ToString())
                .ToArray();
            ConversionSettings.DedupeFormats = formats["dedupe"]!
                .AsArray()
                .Select(format => format!.ToString())
                .ToArray();
            ConversionSettings.IncompatibleFormats = formats["nonredactable"]!
                .AsArray()
                .Select(format => format!.ToString())
                .ToArray();

            var eventHubHost = Environment.GetEnvironmentVariable("REDIS_STREAM_HOST");
            var eventHubPort = Environment.GetEnvironmentVariable("REDIS_STREAM_PORT");
            var eventHubPassword = Environment.GetEnvironmentVariable("REDIS_STREAM_PASSWORD");
            var streamKey = Environment.GetEnvironmentVariable("REDIS_STREAM_KEY")!;
            var dedupeStreamKey = Environment.GetEnvironmentVariable("DEDUPE_STREAM_KEY")!;
            var consumerGroup = Environment.GetEnvironmentVariable("REDIS_STREAM_CONSUMER_GROUP")!;

            var consumerIdentity = ConsumerIdentity.Resolve(
                Environment.GetEnvironmentVariable("CONSUMER_NAME"),
                Environment.MachineName,
                Environment.ProcessId);
            var consumerName = consumerIdentity.Name;
            if (consumerIdentity.IsFallback)
            {
                Log.Warning(
                    "CONSUMER_NAME is missing or blank; using fallback Redis consumer {ConsumerName}",
                    consumerName);
            }

            using var redis = ConnectionMultiplexer.Connect(new ConfigurationOptions
            {
                EndPoints = { $"{eventHubHost}:{eventHubPort}" },
                Password = eventHubPassword
            });

            var database = redis.GetDatabase();
            Log.Information(
                "Connecting to Redis stream {StreamKey} on {Host}:{Port} with consumer group {ConsumerGroup} and consumer {ConsumerName}",
                streamKey,
                eventHubHost,
                eventHubPort,
                consumerGroup,
                consumerName);

            var recoverySettings = RedisConsumerSettings.Load(
                Environment.GetEnvironmentVariable,
                streamKey);
            var redisStreamClient = new StackExchangeRedisStreamClient(database);
            var handler = new FileConversionMessageHandler(
                database,
                streamKey,
                dedupeStreamKey);
            var streamConsumer = new RedisStreamConsumer(
                redisStreamClient,
                handler,
                streamKey,
                consumerGroup,
                consumerName,
                recoverySettings,
                TimeProvider.System);

            await streamConsumer.RunAsync(CancellationToken.None);
        }
        catch (Exception error)
        {
            Log.Fatal(error, "Unhandled error in FOI File Conversion service");
        }
        finally
        {
            Log.CloseAndFlush();
        }
    }

    private static void LoadConversionSettings(IConfiguration configuration)
    {
        ConversionSettings.SyncfusionLicense =
            configuration.GetSection("ConversionSettings:SyncfusionLicense").Value!;

        int.TryParse(
            Environment.GetEnvironmentVariable("FILE_CONVERSION_FAILTUREATTEMPT"),
            out var environmentFailureAttemptCount);
        int.TryParse(
            configuration.GetSection("ConversionSettings:FailureAttemptCount").Value,
            out var failureAttemptCount);
        ConversionSettings.FailureAttemptCount = environmentFailureAttemptCount < 1
            ? failureAttemptCount
            : environmentFailureAttemptCount;

        int.TryParse(
            Environment.GetEnvironmentVariable("FILE_CONVERSION_WAITTIME"),
            out var environmentWaitTimeMilliseconds);
        int.TryParse(
            configuration.GetSection("ConversionSettings:WaitTimeInMilliSeconds").Value,
            out var waitTimeMilliseconds);
        ConversionSettings.WaitTimeInMilliSeconds = environmentWaitTimeMilliseconds == 0
            ? waitTimeMilliseconds
            : environmentWaitTimeMilliseconds;

        int.TryParse(
            configuration.GetSection(
                "ConversionSettings:FileWatcherMonitoringDelayInMilliSeconds").Value,
            out var fileWatcherMonitoringDelayMilliseconds);
        ConversionSettings.FileWatcherMonitoringDelayInMilliSeconds =
            fileWatcherMonitoringDelayMilliseconds;

        int.TryParse(
            Environment.GetEnvironmentVariable("FILE_CONVERSION_OPENFILE_WAITTIME"),
            out var environmentOpenFileWaitTimeSeconds);
        int.TryParse(
            configuration.GetSection("ConversionSettings:OpenFileWaitTimeInSeconds").Value,
            out var openFileWaitTimeSeconds);
        ConversionSettings.OpenFileWaitTimeInSeconds = environmentOpenFileWaitTimeSeconds == 0
            ? openFileWaitTimeSeconds
            : environmentOpenFileWaitTimeSeconds;

        var syncfusionLicense =
            Environment.GetEnvironmentVariable("FILE_CONVERSION_SYNCFUSIONKEY");
        Syncfusion.Licensing.SyncfusionLicenseProvider.RegisterLicense(
            string.IsNullOrEmpty(syncfusionLicense)
                ? ConversionSettings.SyncfusionLicense
                : syncfusionLicense);
    }
}
