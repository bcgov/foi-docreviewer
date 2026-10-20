# pdf-preprocessing — Redis Streams worker

Consumes `PdfPreprocessingRequested` (which carries an `s3://bucket/key` source
URI), reads that PDF from S3, detects **clip-hidden text** (the classic
failed-redaction pattern — text the renderer lays out but a clip path stops from
being painted), re-draws it in place, uploads the restored PDF **back beside
the source** (`<name>.pdf` → `<name>PREPROCESSED.pdf`, same bucket and prefix),
and publishes `PdfPreprocessingCompleted` on a separate stream for the next
service.

No HTTP API, no database. A CLI publishes the input event; Redis holds the
dedup state and both event streams; S3 holds the PDFs.

---

## Quickstart

Prerequisites: Docker with Compose and the AWS CLI v2 on your host.

```bash
make up

# Upload a real PDF; make demo only publishes an event for this object.
AWS_ACCESS_KEY_ID=dev AWS_SECRET_ACCESS_KEY=dev AWS_DEFAULT_REGION=us-east-1 \
  aws --endpoint-url http://localhost:8333 \
  s3 cp ./doc.pdf s3://pdf-preprocessing/incoming/doc.pdf

make demo SOURCE_URI=s3://pdf-preprocessing/incoming/doc.pdf
```

The local stack exposes an authenticated S3-compatible API at
`http://localhost:8333`. It uses access key `dev`, secret key `dev`, region
`us-east-1`, and one bucket: `pdf-preprocessing`. Source and restored objects
share that bucket: `incoming/doc.pdf` becomes `incoming/docPREPROCESSED.pdf`.

Use `make health` to confirm the worker is ready. After a successful restored
document, inspect the output with:

```bash
AWS_ACCESS_KEY_ID=dev AWS_SECRET_ACCESS_KEY=dev AWS_DEFAULT_REGION=us-east-1 \
  aws --endpoint-url http://localhost:8333 \
  s3 ls s3://pdf-preprocessing/incoming/
```

### External S3 configuration (optional)

For an external deployment, `docker compose` loads `.env` into the worker
container. In this local stack, the explicit Compose `environment:` values
intentionally override matching `.env` values, including the local endpoint,
credentials, and region shown above. Therefore, editing `.env` alone cannot
activate external S3 here: use a non-Compose deployment or an explicit Compose
override file that replaces the local values. Configure external storage in
`.env` for that deployment as needed:

```
# real AWS S3
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# ...or an S3-compatible store (BC Gov OCIO object storage):
# S3_ENDPOINT_URL=https://citz-foi-prod.objectstore.gov.bc.ca
# S3_FORCE_PATH_STYLE=true

# OUTPUT_FILENAME_SUFFIX=PREPROCESSED   # default; output lands next to the source
```

The credentials need **write** access to the source bucket — the restored PDF
is written back beside the input.

When using a Compose override file for external storage, recreate the stack
after changing its environment configuration — a running container keeps the
environment it was created with.

A store URL like `https://citz-foi-prod.objectstore.gov.bc.ca/ecc-dev-e/APR-880-880/<uuid>.pdf`
maps to `S3_ENDPOINT_URL=https://citz-foi-prod.objectstore.gov.bc.ca` +
`source_uri=s3://ecc-dev-e/APR-880-880/<uuid>.pdf`.

Expected shape:

```
--- publishing PdfPreprocessingRequested x2 (same job-id)
published 2 x PdfPreprocessingRequested job_id=demo-1 source_uri=s3://…/doc.pdf
--- dedup state in Redis
outcome
restored
spans_restored
24
pages_affected
6
output_uri
s3://pdf-preprocessing/incoming/docPREPROCESSED.pdf
--- PdfPreprocessingCompleted on the output stream
1) 1) "1735300000000-0"
   2) 1) "event"
      2) "{...\"event_type\":\"PdfPreprocessingCompleted\"...}"
--- worker log
... "Preprocessing complete" outcome=restored spans_restored=24
... "Job already processed; nothing to do"
```

Two events in, one `PdfPreprocessingCompleted` out. The second delivery is a
logged no-op — the idempotency guard doing its job.

---

## Architecture

```
python -m cli publish --source-uri s3://bucket/key [--job-id <id>] [--count N]
  └→ XADD pdf.preprocessing.requests "PdfPreprocessingRequested" {job_id, source_uri}

[worker] XREADGROUP pdf.preprocessing.requests
  └→ S3 GetObject  source_uri        (HeadObject size cap, %PDF- check)   [the work]
  └→ core.pipeline.run_pipeline      (local scratch in WORK_DIR)
  └→ S3 PutObject  <source>PREPROCESSED.pdf   (same bucket/prefix; only if hidden text found)
  └→ HSETNX preprocessing:<job_id> outcome ...   (idempotency guard)
  └→ XADD pdf.preprocessing.completed "PdfPreprocessingCompleted"
         {job_id, outcome, spans_restored, pages_affected, output_uri}
  └→ XACK

[next service] XREADGROUP pdf.preprocessing.completed → ...
```

`outcome` is `restored` (hidden text found and re-drawn; `output_uri` set) or
`clean` (none found; nothing uploaded, `output_uri` null). An S3 error or
malformed PDF raises → the consumer retries → dead-letters to
`pdf.preprocessing.requests:dlq`.

The worker **publishes** `PdfPreprocessingCompleted` but does not consume it —
that stream belongs to the next service. `STREAM_NAME` (input) and
`OUTPUT_STREAM_NAME` (output) are kept separate for exactly this reason.

The local development stack has four components:

- `seaweedfs` provides the authenticated S3-compatible object store and keeps
  data in the `seaweeddata` volume.
- `bucket-init` is a profile-gated AWS CLI job that creates and verifies
  `pdf-preprocessing` before a local workflow uses it.
- `redis` stores both streams and the handler's idempotency state.
- `worker` consumes requests, restores clipped text, writes output to the same
  bucket, and publishes completion events.

---

## How restoration works (`core/pipeline.py`, `core/clip_hidden_text.py`)

`core/pipeline.py` opens the PDF once and runs every registered detector on
each page in order. A detector only needs to provide `restore_page(page) ->
int`; the pipeline handles rotation normalization, saving, and combined plus
per-detector results.

Each page's text is extracted twice, identically except one pass honors clip
paths (`TEXT_MEDIABOX_CLIP`) and the other doesn't. A span present only in the
no-clip pass is text a clip is hiding. Each such span is re-drawn on top of the
page, outside all clips, in its own font/size/colour (closest Base-14 face,
since embedded subset fonts can't be reused). Output is written only when
hidden text is found.

Not detected: text hidden by an opaque box drawn *over* it (no clip involved),
or invisible render-mode-3 text — different failure modes.

`core/s3.py` wraps boto3 (`fetch_pdf` / `upload_pdf`), each call run in
`asyncio.to_thread` so the sync SDK doesn't block the event loop. It checks
`HeadObject` size against `MAX_PDF_BYTES` and the `%PDF-` header before
trusting the bytes. Credentials and region come from the standard boto3 chain.
The **endpoint** is a setting: unset = real AWS S3; set `S3_ENDPOINT_URL`
(+ `S3_FORCE_PATH_STYLE=true`) for an S3-compatible store like BC Gov OCIO
object storage or MinIO.

---

## One trace across the hops

Trace context rides in a `traceparent` field on the envelope. The producer
injects whatever span is current; the consumer extracts it and makes its
message span current, so the `PdfPreprocessingCompleted` it publishes is a
child of the message being handled:

```
[cli.publish]
  └── [publish PdfPreprocessingRequested]
        └── [consume PdfPreprocessingRequested]        (worker)
              └── [publish PdfPreprocessingCompleted]
```

Point `OTEL_EXPORTER_OTLP_ENDPOINT` at a collector to see it, or set
`OTEL_EXPORTER_OTLP_ENDPOINT_ENABLE_FALLBACK=True` for console spans.

The rule to keep if you touch the consumer: the message span must be made
**current** (`start_as_current_span`), not held detached. A detached span
exports identically and silently orphans every downstream hop.

---

## Health

The worker serves one endpoint on `HEALTH_PORT` (8000 in compose):

```bash
make health     # 200 {"status":"ok","redis":"ok"} or 503 {"status":"degraded",...}
```

~40 lines of `asyncio.start_server` in `health/server.py`, not a web framework.

---

## Developer guide

### Local operations

```bash
make health                         # worker and Redis health
make logs                           # follow worker logs
make init-bucket                    # re-run idempotent bucket setup
make down                           # stop the local stack
```

Failed source-object requests are retried and then sent to the dead-letter
stream. Inspect it with:

```bash
docker compose exec redis redis-cli -a redis --no-auth-warning -n 1 \
  XRANGE pdf.preprocessing.requests:dlq - +
```

### Tests and formatting

```bash
make test       # unit tests
make test-all   # unit and integration tests (requires Docker)
make lint
make fmt
```

### Extending the service

The document-processing boundary is the `fetch_pdf` → `restore_pdf` →
`upload_pdf` sequence in
`messaging/consumer/handlers/pdf_preprocessing_requested.py`. A new processing
step should preserve the input/output URI contract and update the event payloads
under `messaging/models/events/` when its result changes.

To add a *new* event type it's the usual four-file edit:

1. `messaging/models/events/` — the payload model.
2. `messaging/models/envelope.py` — add it to the `Literal` and the
   `EventPayload` union.
3. `messaging/consumer/handlers/` — the handler.
4. `messaging/consumer/dispatcher.py` — register it in `HANDLERS`.

Two rules:

- **Handlers must be idempotent.** Redis Streams delivers at least once. Guard
  with a conditional write, and put the early return *before* any publish.
- **Don't publish upstream from a handler.** A handler that republishes what it
  consumes onto the same stream is an infinite loop.

---

## Known delivery limitation

The handler writes its dedup state, then publishes. Those two steps are not
atomic: if the publish fails after the state write, the retry sees the guard
and skips the publish, so `PdfPreprocessingCompleted` is lost. That's the
write-then-publish problem; the real answer is a transactional outbox — persist
the outgoing event in the same write as the state and let a relay drain it.
It is deliberately not implemented because it adds a persistent relay and its
associated operational complexity. The failure mode is named in the handler
docstring.

---

## Reliability

At-least-once consumer with in-process retry (`CONSUMER_MAX_RETRIES`,
exponential `CONSUMER_RETRY_BACKOFF_MS`), then dead-letter to
`<STREAM_NAME>:dlq`. Malformed envelopes are dead-lettered with no retries.
`XAUTOCLAIM` reclaims messages orphaned by a killed worker; one already past
the retry limit is dead-lettered rather than looped forever.

Unit: `core.clip_hidden_text` and `core.pipeline` restoration on generated
PDFs, `core.s3` fetch/upload
against a `moto` mock, envelope/dispatcher/settings logic. Integration (real
Redis via testcontainers, S3 faked): the handler, the full `cli → consume →
publish` round trip, one trace across the hops, and the DLQ path.
