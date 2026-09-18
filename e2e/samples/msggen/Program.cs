using System.IO.Compression;
using MsgKit;
using MsgKit.Enums;

// Usage: msggen <output.msg> <attachmentCount>
var output = args[0];
var count = int.Parse(args[1]);
var work = Path.Combine(Path.GetTempPath(), "msggen-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(work);

static byte[] Png(byte r, byte g, byte b)
{
    // 1x1 RGB PNG built by hand so no imaging library is needed.
    static byte[] Chunk(string type, byte[] data)
    {
        var t = System.Text.Encoding.ASCII.GetBytes(type);
        var crcInput = t.Concat(data).ToArray();
        uint crc = 0xFFFFFFFF;
        foreach (var by in crcInput) { crc ^= by; for (var i = 0; i < 8; i++) crc = (crc & 1) != 0 ? (crc >> 1) ^ 0xEDB88320 : crc >> 1; }
        crc ^= 0xFFFFFFFF;
        var len = BitConverter.GetBytes(data.Length).Reverse().ToArray();
        return len.Concat(t).Concat(data).Concat(BitConverter.GetBytes(crc).Reverse()).ToArray();
    }
    var ihdr = new byte[] { 0, 0, 0, 1, 0, 0, 0, 1, 8, 2, 0, 0, 0 };
    var raw = new byte[] { 0, r, g, b };
    using var ms = new MemoryStream();
    using (var z = new ZLibStream(ms, CompressionLevel.Optimal, true)) z.Write(raw);
    var sig = new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 };
    return sig.Concat(Chunk("IHDR", ihdr)).Concat(Chunk("IDAT", ms.ToArray())).Concat(Chunk("IEND", Array.Empty<byte>())).ToArray();
}

var sender = new Sender("sender@example.test", "Test Sender");
const string recipientEmail = "recipient@example.test"; const string recipientName = "Test Recipient";

var attachmentPaths = new List<string>();
for (var i = 1; i <= count; i++)
{
    var child = new Email(sender, $"Forwarded message {i:00}", draft: false);
    child.Recipients.AddTo(recipientEmail, recipientName);
    child.Subject = $"Forwarded message {i:00}";
    child.BodyText = $"This is generic forwarded message number {i} used by the pipeline e2e test.";
    child.BodyHtml = $"<html><body><p>This is generic forwarded message number {i} used by the pipeline e2e test.</p></body></html>";
    child.SentOn = new DateTime(2025, 1, i, 9, 0, 0, DateTimeKind.Utc);
    var path = Path.Combine(work, $"Forwarded message {i:00}.msg");
    child.Save(path);
    attachmentPaths.Add(path);
}

var img1 = Path.Combine(work, "image001.png");
var img2 = Path.Combine(work, "image002.png");
File.WriteAllBytes(img1, Png(200, 30, 30));
File.WriteAllBytes(img2, Png(30, 30, 200));

var parent = new Email(sender, "Test conversion", draft: false);
parent.Recipients.AddTo(recipientEmail, recipientName);
parent.Subject = "Test conversion";
parent.SentOn = new DateTime(2025, 2, 1, 9, 0, 0, DateTimeKind.Utc);
parent.BodyText = $"Generic e2e sample with {count} forwarded .msg attachments and two inline images.";
parent.BodyHtml = "<html><body>" +
    $"<p>Generic e2e sample with {count} forwarded .msg attachments and two inline images.</p>" +
    "<p><img src=\"cid:image001.png@e2e\" width=\"1\" height=\"1\"/> <img src=\"cid:image002.png@e2e\" width=\"1\" height=\"1\"/></p>" +
    "</body></html>";
parent.Attachments.Add(img1, -1, true, "image001.png@e2e");
parent.Attachments.Add(img2, -1, true, "image002.png@e2e");
foreach (var p in attachmentPaths) parent.Attachments.Add(p);
parent.Save(output);
Directory.Delete(work, true);
Console.WriteLine($"wrote {output} ({new FileInfo(output).Length} bytes) with {count} .msg attachments + 2 inline images");
