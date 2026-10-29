namespace MCS.FOI.MSGToPDF;

internal static class MessageDateFormatter
{
    internal static string FormatSentOn(DateTime? sentOn, DateTime? creationTime)
    {
        var source = sentOn.HasValue && sentOn.Value != DateTime.MinValue
            ? sentOn
            : creationTime;

        if (!source.HasValue || source.Value == DateTime.MinValue ||
            source.Value.Kind == DateTimeKind.Unspecified)
        {
            return "Unknown";
        }

        // MsgReader 4.5 exposes MAPI FILETIME and transport-header instants as
        // Local DateTime values. Respect Kind instead of reinterpreting those
        // wall-clock fields as UTC or skipping conversion on a Pacific host.
        var instant = new DateTimeOffset(source.Value);
        var pacificTime = TimeZoneInfo.ConvertTime(
            instant, TimeZoneInfo.FindSystemTimeZoneById("America/Vancouver"));

        // Preserve the existing date format while using a label valid in history.
        return pacificTime.DateTime + " Pacific Time";
    }
}
