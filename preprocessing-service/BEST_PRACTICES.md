# PDF Preprocessing Engineering Practices

This guide records the practices that keep the PDF preprocessing worker safe,
observable, and reliable in the FOI document-review pipeline. For local setup
and operations, see [README.md](README.md); for contribution workflow, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Service architecture

The worker consumes a source-object event, restores clip-hidden text when
present, and publishes the result for the next pipeline stage.

| Component | Location | Responsibility |
| --- | --- | --- |
| Event contracts | `messaging/models/` | Validates request and completion envelopes. |
| Consumer and dispatcher | `messaging/consumer/` | Reads Redis Streams, retries failures, and routes event types. |
| PDF handler | `messaging/consumer/handlers/pdf_preprocessing_requested.py` | Fetches, restores, uploads, records idempotency state, and publishes completion. |
| Object storage | `core/s3.py` | Validates and transfers PDFs through boto3. |
| PDF restoration | `core/hidden_text.py` | Detects and redraws clipped text. |
| Runtime services | `config/`, `health/`, `main.py` | Settings, logs, traces, health, and worker lifecycle. |

Keep these boundaries intact. The consumer should not contain PDF logic, and a
handler should not manipulate Redis Streams internals directly.

## Object flow and SeaweedFS

Local Compose uses SeaweedFS as an authenticated S3-compatible store. The
worker connects internally to `http://seaweedfs:8333` with path-style
addressing; developers connect from the host at `http://localhost:8333`.

Both source and restored PDFs live in `pdf-preprocessing`:

```text
s3://pdf-preprocessing/incoming/doc.pdf
  -> s3://pdf-preprocessing/incoming/docPREPROCESSED.pdf
```

`bucket-init` creates the bucket idempotently, but it never uploads an input
PDF. Upload a real document before publishing a demo event. A `HeadObject` 404
means the source object is missing, not that the worker cannot reach SeaweedFS.

## Safe asynchronous PDF processing

The handler follows this sequence:

```text
fetch_pdf -> restore_pdf -> upload_pdf -> record idempotency state -> publish completion
```

`boto3` is synchronous, so `core/s3.py` runs transfer calls through
`asyncio.to_thread`. Do not move S3 I/O onto the consumer event loop: doing so
would delay stream polling and health responses.

Treat untrusted PDFs defensively. `fetch_pdf` checks the object size against
`MAX_PDF_BYTES` and verifies the `%PDF-` header before restoration. Keep those
checks, or replace them with controls of equal strength. Temporary source and
output files belong in `WORK_DIR` and must be cleaned up even when processing
fails.

## Redis Streams reliability

Redis Streams has at-least-once delivery semantics. A redelivery is normal and
must not produce another completion event.

- The handler uses `HSETNX preprocessing:<job_id>` as its idempotency guard.
  If another delivery already set it, the handler returns before publishing.
- Handler failures retry with exponential backoff up to
  `CONSUMER_MAX_RETRIES`; exhausted or malformed messages go to
  `<STREAM_NAME>:dlq`.
- `XAUTOCLAIM` recovers messages left pending by a crashed worker.
- Input and output streams stay separate: this worker consumes
  `pdf.preprocessing.requests` and publishes
  `pdf.preprocessing.completed`.

The state write and completion publish are separate operations. If state is
recorded and publishing then fails, a retry sees the guard and does not publish
the completion event. This is a known write-then-publish failure window. A
transactional outbox is required if downstream delivery must be atomic with
the idempotency record.

## Tracing, logging, and health

Use `config.logging.get_logger` for structured logs. Log meaningful identifiers
such as `job_id`, `correlation_id`, `message_id`, event type, retry attempt, and
object URI; never log credentials or document contents.

Trace context travels in `EventEnvelope.traceparent`. Producers inject ambient
context; consumers must create their message span with
`start_as_current_span`. A detached span can look valid in logs while silently
breaking parentage for completion events.

The health endpoint checks Redis rather than returning an unconditional 200.
A failed consumer task should stop the worker, and an unavailable Redis
connection should surface as degraded health so an orchestrator can react.

## Configuration and secrets

Use `config.settings.get_settings()` rather than reading environment variables
ad hoc. Settings are validated once and cached. Keep setting names stable when
changing deployments.

Local Compose deliberately supplies these S3 values after `.env`, so local
development cannot accidentally point at an external object store:

```text
S3_ENDPOINT_URL=http://seaweedfs:8333
S3_FORCE_PATH_STYLE=true
AWS_ACCESS_KEY_ID=dev
AWS_SECRET_ACCESS_KEY=dev
AWS_DEFAULT_REGION=us-east-1
```

Production credentials must come from the deployment's secret mechanism or IAM
identity. Never add credentials to `.env` examples, logs, test fixtures, or
commits.

## Testing and review

Use fast unit tests for parsing, settings, PDF restoration, S3 error handling,
and handler decisions. Use integration tests for the Redis consumer, retries,
dead-lettering, trace propagation, and end-to-end event flow.

Before review, run:

```bash
make fmt
make lint
make test
make test-all
docker compose --profile init config
```

For changes to local object storage or document flow, also run the local stack:
upload a real PDF, publish a request, verify the restored object when
applicable, and inspect the completion stream and DLQ.
