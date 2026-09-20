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
| `messageprocessor.go` | `main()` → `run()`: opens the daily log file, takes the run lock, builds the clients, hands the ActiveMQ source to `pipeline.Run` |
| `config/` | `Load()`: every tunable with a legacy-equivalent default; bad values log `CONFIG_DEFAULT` |
| `runlock/` | Lock file with PID; a lock from a dead PID or older than 2 × `ocrjobtimeoutseconds` is taken over |
| `logx/` | `Event(marker, k, v, …)`: one `MARKER k=v` line per event |
| `httpx/` | `DoWithRetry`: 429/5xx/transport retry with `Retry-After` or capped backoff; `CodedError` |
| `httpservices/messagedequeue.go` | `ActiveMQSource.Next`: one destructive REST GET per call, mutex-guarded, capped by `activemqbatchsize` |
| `pipeline/` | `Run` (worker pool, `RUN_SUMMARY`) and `Process` (download → submit → poll → result → upload, status contract) |
| `azureservices/azureocrservice.go` | Azure Document Intelligence client: `Submit`, `Poll`, `ResultPDF` |
| `s3services/s3services.go` | Presigned GET/PUT (AWS SDK v1) and `Store` (download/upload with retry) |
| `docreviewerocrservice/docreviewerocrservice.go` | `Client.Post`: `DocReviewAudit` rows to the reviewer API, soft or hard retry |
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
| `activemqbatchsize` | config | Messages pulled per run; `0` = until the queue is empty. Default `0`; recommended `20` |
| `maxconcurrentocrjobs` | config | Documents processed in parallel. Default `1`; recommended `5` |
| `ocruploadconcurrency` | config | Concurrent S3 PUTs. Default `1`; recommended `3` |
| `azureanalyzeratelimit` | config | Analyze POSTs per second across all workers; `0` = unlimited. Default `0`; recommended `2` |
| `azurepollintervalseconds` | config | Base delay between status polls; a `Retry-After` header overrides it. Default `5` |
| `azurepollmaxattempts` | config | Give up polling after this many status reads (120 × 5s = 10 min). Default `120` |
| `azuremaxretries` | config | Retries per HTTP call on 429/5xx/transport error; `0` = none. Default `0`; recommended `5` |
| `azureretrybaseseconds` | config | Backoff base: `min(base * 2^n + jitter, azureretrymaxseconds)`. Default `2` |
| `azureretrymaxseconds` | config | Backoff ceiling. Default `60` |
| `ocrjobtimeoutseconds` | config | Hard deadline for download → upload of one document. Default `900` |
| `azurehttptimeoutseconds` | config | Azure HTTP client timeout. Default `120` |
| `s3httptimeoutseconds` | config | S3 HTTP client timeout. Default `120` |
| `reviewerapitimeoutseconds` | config | Reviewer API HTTP client timeout. Default `30` |
| `activemqhttptimeoutseconds` | config | ActiveMQ REST HTTP client timeout. Default `30` |
| `azureusebase64source` | config | `true` = `base64Source` (default); `false` = `urlSource` with a presigned GET (only if Azure can reach the S3 endpoint from the internet) |
| `runlockpath` | config | Overlap guard; default `<logfilepath>azureocrservice.lock` |

### Status contract

| Event | Status | `message` |
| --- | --- | --- |
| Analyze accepted | `azureocrrequestcreated` | `{"apimRequestID","operationLocation"}` |
| First `running` poll | `ocrjobrunning` (once) | `{"apimRequestID"}` |
| Result PDF retrieved | `ocrjobsucceeded` | `{"apimRequestID","pdfSize"}` |
| S3 upload done | `ocrfileuploadsuccess` | `{"apimRequestID"}` + `ocrfilepath`, `ocrfilesize` |
| Any failure | `ocrjobfailed` | `{"stage":"download|submit|poll|result|upload","code","reason","attempts"}` |

`operationLocation` is kept so a completed Azure result (valid 24 h) can be fetched by hand without re-submitting.
Only `ocrfileuploadsuccess` and `ocrjobfailed` are hard posts (retried until they succeed or the process gives up); the others are best-effort.

### Log markers

`RUN_START`, `RUN_SUMMARY`, `RUNLOCK_HELD`, `RUNLOCK_STALE`, `RUNLOCK_ERROR`, `CONFIG_DEFAULT`, `DEQUEUED`, `DEQUEUE_BAD_MESSAGE`,
`DEQUEUE_TIMEOUT`, `DEQUEUE_RETRY`, `DEQUEUE_ERROR`, `DOWNLOAD_OK`, `AZURE_SUBMIT`, `AZURE_POLL`, `AZURE_RETRY`, `AZURE_RESULT_OK`,
`S3_RETRY`, `REVIEWER_RETRY`, `REVIEWER_POST_OK`, `REVIEWER_POST_FAILED`, `UPLOAD_OK`, `JOB_DONE`, `JOB_FAILED`. Every line carries
`documentid` where applicable; `RUN_SUMMARY` carries `pulled`, `succeeded`, `failed`, `retries`, `http429`, `dequeueError`, `totalms`
and `ids=<documentid>:ok|failed:<stage>,…` — the run's manifest. Transport errors are URL-redacted; presigned URLs and secrets are
never logged.

Reconcile a run: every `DEQUEUED documentid=X` must have a `JOB_DONE` or `JOB_FAILED` for `X`; one without either was in flight when
the process died and must be re-queued.

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

## Running on the Windows VM

Build: `set GOOS=windows& set GOARCH=amd64& go build -o azureocrservice.exe .` (or cross-compile from Linux with `GOTOOLCHAIN=auto GOOS=windows GOARCH=amd64 go build -o azureocrservice.exe .`).

Task Scheduler:

- Trigger: repeat every 5 minutes, indefinitely.
- Action: `azureocrservice.exe`, **Start in** = the folder containing `.env` (the binary loads `.env` from the working directory).
- Settings: **Do not start a new instance** if the task is already running; run whether the user is logged on or not.
- The binary also takes a lock file (`runlockpath`); a second instance logs `RUNLOCK_HELD` and exits 0 without touching the queue, so a mis-configured scheduler cannot double the Azure rate.
- Environment variables set at the system level must be UPPERCASE (`AZUREMAXRETRIES`, …); `.env` keys may stay lowercase.
- Stop a run cleanly with Ctrl+C / `taskkill` (no `/F`): in-flight documents post `ocrjobfailed code=Interrupted` and `RUN_SUMMARY` is written.

Each run pulls up to `activemqbatchsize` messages and exits; latency for a new message is at most one scheduler interval.

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

Unit tests live beside the code (`go test ./...`); external calls are stubbed with `httptest.Server`. Run with `-race` for `pipeline/` and `httpservices/`.

End to end: `e2e-ocr/run.sh` runs the real worker against ActiveMQ, SeaweedFS, Postgres and a mock Azure (see `e2e-ocr/README.md`).

### Load test (dev, real Azure)

Fill in from `RUN_SUMMARY` / `JOB_*` lines after each run. Raise `concurrency`/`ratelimit` until `http429 > 0`, then back off one step and record that as the production default.

| N | batchsize | concurrency | ratelimit | http429 | failed | p50 / p95 doc s | run s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 10 | 2 | 1 | | | | |
| 20 | 20 | 5 | 2 | | | | |
| 50 | 20 | 5 | 2 | | | | (3 runs) |
| 100 | 20 | 10 | 4 | | | | (5 runs) |

After each run every `DEQUEUED` id must have a `JOB_DONE`/`JOB_FAILED` line and a matching `ocrfileuploadsuccess`/`ocrjobfailed` row in `DocumentOCRJob`.

## Related

- Upstream producer: [`computingservices/OCRServices`](../OCRServices)
- Status consumer: `reviewer_api` `POST /api/documentocrjob` → `DocumentOCRJob`
- Architecture: [`docs/FOI_Current_Document_Processing_Architecture.md`](../../docs/FOI_Current_Document_Processing_Architecture.md)
