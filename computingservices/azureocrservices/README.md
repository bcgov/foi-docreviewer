# azureocrservices

Go worker that turns uploaded FOI documents into searchable PDFs using
[Azure Document Intelligence](https://learn.microsoft.com/azure/ai-services/document-intelligence/)
(`prebuilt-read` model). It is the last stage of the document-processing
pipeline: it consumes OCR jobs from ActiveMQ, sends the PDF to Azure, stores the
OCR'd PDF back in S3, and reports each lifecycle step to the reviewer API.

Deployed as an Azure Function on a timer trigger (every 5 minutes, see
[`FOIDocumentOCRTimerTrigger/function.json`](FOIDocumentOCRTimerTrigger/function.json)).
Each run drains the queue and exits.

For where this sits in the wider pipeline, see
[`docs/document-processing-message-flow.md`](../../docs/document-processing-message-flow.md).

## What it does

```text
ActiveMQ (foidococrqueue)
   │  JSON QueueMessage {documentId, documentMasterId, ministryRequestId, S3FilePath, compressedS3FilePath}
   ▼
messageprocessor.go ── drain queue via ActiveMQ REST (GET until 204)
   │
   │  for each message:
   ├─ 1. pick compressedS3FilePath, fall back to S3FilePath
   ├─ 2. presign GET → download PDF bytes from S3
   ├─ 3. POST base64 PDF to Azure  .../prebuilt-read:analyze?output=pdf
   │        → status "azureocrrequestcreated"
   ├─ 4. poll Operation-Location every 5s
   │        → "ocrjobrunning" | "ocrjobsucceeded" | "ocrjobfailed"
   ├─ 5. GET .../analyzeResults/{id}/pdf → searchable PDF bytes
   ├─ 6. presign PUT → upload to S3 as <name>OCR.pdf next to the source
   │        → "ocrfileuploadsuccess" (with ocrfilepath + ocrfilesize)
   ▼
reviewer API  POST /api/documentocrjob  (header X-FOI-OCR-Secret)
   → persisted in DocumentOCRJob
```

Every status transition is pushed to the reviewer API so the review UI can show
OCR progress and the final output path.

## Dequeue process in detail

Consumption is done over the **ActiveMQ REST API**, not a JMS/STOMP/AMQP
client. Code: [`httpservices/messagedequeue.go`](httpservices/messagedequeue.go).

### URL construction

```go
url := fmt.Sprintf("%s://%s&clientId=%s", activeMQBaseURL, queueName, activemqclientid)
```

With `activeMQBaseURL=https://mq.example.com/api/message?destination=queue`,
`foidococrqueue=foidococrqueue` and `activemqclientid=azureocr` this produces:

```text
https://mq.example.com/api/message?destination=queue://foidococrqueue&clientId=azureocr
```

The literal `://` in the format string is the `queue://` part of the ActiveMQ
destination, so `activeMQBaseURL` must end with `destination=queue` (no
trailing `://`). The `clientId` keeps a stable REST consumer session on the
broker between polls, so ActiveMQ hands out the next message rather than
redelivering the same one.

### Loop

```text
ProcessMessage()
  messages := []
  loop:
    GET url   (Basic auth, 30s client timeout)
    ├─ 200 + JSON body      → unmarshal into QueueMessage, append, loop again
    ├─ 204 No Content       → queue empty, break
    ├─ context deadline hit → count timeout; break once maxTimeouts (=1) reached
    └─ any other error/
       non-200 status       → return error (caller log.Fatal's, run aborts)
  return messages
```

Key properties:

- **Drain-then-process.** `ProcessMessage` pulls *every* available message into
  a slice before `main()` starts any OCR. Nothing is processed while the queue
  is being read.
- **Consume on read.** The ActiveMQ REST `GET` is a destructive receive: the
  message is acknowledged and removed from the queue as soon as the broker
  returns it. There is no ack after OCR completes, so if the process dies (or
  `log.Fatal`s) after dequeue and before upload, those messages are **lost**
  from the queue. The `DocumentOCRJob` audit table is the only place to detect
  this (status stuck at `azureocrrequestcreated`/`ocrjobrunning`, or no row).
- **Two exit signals.** Normally the broker returns `204` when empty. If instead
  the request hangs and hits the 30s client timeout, that is treated as "no
  more messages" after one occurrence (`maxTimeouts = 1`). Any other HTTP error
  (401, 5xx, connection refused) aborts the whole run.
- **Not concurrent.** One `GET` at a time; one consumer per run. Parallel runs
  of this function against the same queue would work (broker distributes
  messages) but are not how it's deployed.
- **Message body** is expected to be a single JSON object matching
  `types.QueueMessage`. Anything that fails to unmarshal aborts the run — the
  offending message has already been consumed at that point.

### Debugging a dequeue problem

1. Check the log file for the `URL:` line and confirm it reads
   `...destination=queue://<name>&clientId=<id>`. A malformed
   `activeMQBaseURL` is the most common cause of a 400/404.
2. `HTTP Status Code: 401` → wrong `activeMQUserName`/`activeMQPassword`.
3. `HTTP Status Code: 204` immediately with messages visibly in the queue →
   another consumer (or a stale `clientId` session) has them. Check the
   broker's consumer list for the queue.
4. `No messages received within the timeout` on every run → the broker is
   holding the connection open (long-poll) rather than returning 204. Add
   `&timeout=<ms>` to `activeMQBaseURL` if the broker supports it, or the run
   will always spend 30s idle before exiting.
5. Messages consumed but no OCR happened → look for `failed to unmarshal
   message` in the log; the payload shape from `OCRServices` and
   `types.QueueMessage` have diverged.

## Package layout

| Path | Responsibility |
| --- | --- |
| `messageprocessor.go` | `main()`: opens the daily log file, drains the queue, runs OCR per message |
| `httpservices/messagedequeue.go` | Fetches messages from the ActiveMQ REST endpoint until the queue is empty |
| `azureservices/azureocrservice.go` | Azure Document Intelligence client: submit, poll, download searchable PDF, upload to S3, emit status |
| `s3services/s3services.go` | Presigned GET/PUT URL generation (AWS SDK v1, path-style, S3-compatible endpoint) and upload |
| `docreviewerocrservice/docreviewerocrservice.go` | Posts `DocReviewAudit` status records to the reviewer API |
| `types/` | `QueueMessage`, `DocReviewAudit`, `S3Details`, Azure `AnalyzeResults` structs |
| `utils/utils.go` | `ViperEnvVariable(key)`: reads `.env` + process environment via viper |
| `FOIDocumentOCRTimerTrigger/` | Azure Functions timer binding |

## Configuration

Config is read from a `.env` file in the working directory and/or process
environment variables (`utils.ViperEnvVariable`). Keys the code actually reads:

| Key | Used by | Purpose |
| --- | --- | --- |
| `s3endpoint` | s3services | S3-compatible endpoint URL |
| `s3accesskey` / `s3secretkey` | s3services | Static S3 credentials |
| `s3region` | s3services | Region string (e.g. `us-east-1`) |
| `azuresubcriptionkey` | azureservices | `Ocp-Apim-Subscription-Key` for Azure (note the spelling: `subcription`) |
| `azuredocumentocraiendpoint` | azureservices | Azure Document Intelligence base URL, no trailing slash |
| `activeMQBaseURL` | httpservices | Scheme+host of the ActiveMQ REST API, e.g. `https://mq.example.com/api/message` — the code appends `://<queue>&clientId=<id>` |
| `activeMQUserName` / `activeMQPassword` | httpservices | Basic auth for ActiveMQ |
| `foidococrqueue` | httpservices | Queue name to consume from |
| `activemqclientid` | httpservices | Client id passed to ActiveMQ |
| `docreviewerocrapiendpoint` | docreviewerocrservice | Reviewer API base URL; `/api/documentocrjob` is appended |
| `docreviewerocrapisecret` | docreviewerocrservice | Sent as `X-FOI-OCR-Secret` |
| `logfilepath` | messageprocessor | Directory for `<YYYY-M-D>dococrlog.txt`; stdout is redirected there |

[`sample.env`](sample.env) contains exactly these keys. To verify they stay in
sync with the code:

```bash
diff <(grep -oE '^[a-zA-Z0-9]+' sample.env | sort) \
     <(grep -rhoE 'ViperEnvVariable\("[^"]+"\)' --include=*.go . | sed -E 's/.*"(.*)".*/\1/' | sort)
```

## Quick start (local)

Prerequisites: Go 1.23+, reachable ActiveMQ, S3-compatible storage, an Azure
Document Intelligence resource, and a running reviewer API.

```bash
cd computingservices/azureocrservices
cp sample.env .env          # then fill in every key from the table above
mkdir -p logs && echo 'logfilepath=./logs/' >> .env
go mod tidy
go run .
```

Output goes to `logs/<date>dococrlog.txt`, not the terminal (stdout is
redirected in `main()`). Tail it in another shell:

```bash
tail -f logs/*dococrlog.txt
```

To exercise a single document, publish a message to the queue with the
reviewer's ActiveMQ contract:

```json
{
  "ministryRequestId": 123,
  "requestNumber": "EDU-2025-00001",
  "ministryCode": "EDU",
  "documentId": 456,
  "documentMasterId": 789,
  "S3FilePath": "https://s3.example.com/bucket/path/file.pdf",
  "compressedS3FilePath": "https://s3.example.com/bucket/path/file-compressed.pdf"
}
```

The OCR'd file will land at `.../file-compressedOCR.pdf` in the same bucket.

## Development guidelines

### Build, vet, format

```bash
gofmt -l .        # must print nothing
go vet ./...
go build ./...
```

Run these before every commit. There is no CI gate for this service yet, so
this is the safety net.

### Conventions

- **Config access:** always go through `utils.ViperEnvVariable`. Don't call
  `os.Getenv` directly; keep `.env` and real env interchangeable.
- **New env keys:** add them to `sample.env` *and* the table in this README in
  the same commit.
- **Status names** sent to `/api/documentocrjob` are a contract with
  `reviewer_api` and the `DocumentOCRJob` table. Don't rename or add one
  without a matching API/DB change. Current set:
  `azureocrrequestcreated`, `ocrjobrunning`, `ocrjobsucceeded`,
  `ocrjobfailed`, `ocrfileuploadsuccess`.
- **Queue contract:** `types.QueueMessage` must stay in sync with what
  `OCRServices` publishes. Field names are JSON-tagged; change both ends
  together.
- **S3 paths** in messages are full URLs; `s3services.GetS3Details` splits
  them into bucket + key. Keep that parsing in one place.
- **Errors:** wrap with `fmt.Errorf("...: %w", err)` so callers can
  `errors.Is`. Prefer returning errors over `log.Fatal` — several places still
  `log.Fatal` inside helpers, which kills the whole batch on one bad message.
  Don't add more; convert existing ones when you touch them.
- **Logging:** `fmt.Println` to the redirected stdout is the current pattern.
  Never log the subscription key, S3 secrets, presigned URLs, or the API
  secret. Presigned URLs embed credentials.
- **Azure API version** is hard-coded (`2024-11-30`) in `azureocrservice.go`.
  If you bump it, update both the `:analyze` URL and the `/pdf` result URL.

### Things to know before changing behaviour

- The worker is **not idempotent**: reprocessing a message re-submits to Azure
  (billable) and overwrites the `...OCR.pdf` object.
- Polling has **no timeout**: `getAnalysisResults` loops until Azure returns a
  terminal status. A stuck Azure job blocks the whole run.
- The HTTP client timeout is 30s per request. Large PDFs are base64-encoded in
  memory and posted in one request; very large files may need chunking or the
  URL-source variant of the Azure API.
- One `ProcessMessage` call drains the entire queue into memory before any OCR
  starts. Fine for the current volume; revisit if queue depth grows.
- `.idea/` is local IDE state and should not be committed.

### Testing

There are no unit tests yet. When adding them:

- Put `_test.go` files beside the code they test.
- Wrap external calls (Azure, S3, ActiveMQ, reviewer API) behind `http.Client`
  or interfaces so they can be stubbed with `httptest.Server`.
- Good first targets: `GetS3Details` URL parsing, `GeneratePresignedUploadURL`
  key suffixing (`file.pdf` → `fileOCR.pdf`), and `getAnalysisResults` status
  handling.

The repo-level e2e harness (`e2e/`) covers the upstream pipeline up to OCR
dispatch; this service is exercised against real Azure in dev/test
environments.

## Related

- Upstream producer: [`computingservices/OCRServices`](../OCRServices)
- Status consumer: `reviewer_api` `POST /api/documentocrjob` → `DocumentOCRJob`
- Architecture: [`docs/FOI_Current_Document_Processing_Architecture.md`](../../docs/FOI_Current_Document_Processing_Architecture.md)
