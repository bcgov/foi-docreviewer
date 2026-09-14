namespace MCS.FOI.S3FileConversion.Messaging;

public enum MessageDisposition
{
    Succeeded,
    PermanentFailure,
    RetryableFailure
}

public sealed record MessageHandlingResult(
    MessageDisposition Disposition,
    Exception? Error)
{
    public static MessageHandlingResult Succeeded() =>
        new(MessageDisposition.Succeeded, null);

    public static MessageHandlingResult Permanent(Exception error) =>
        new(MessageDisposition.PermanentFailure, error);

    public static MessageHandlingResult Retryable(Exception error) =>
        new(MessageDisposition.RetryableFailure, error);
}
