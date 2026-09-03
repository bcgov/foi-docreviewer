# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

A Python Redis Streams **worker** (no HTTP API, no database). It consumes
`PdfPreprocessingRequested` (which carries an `s3://bucket/key` source URI),
reads that object from S3, detects and re-draws clip-hidden text (failed
redactions), uploads the restored PDF back beside the source
(`<name>.pdf` → `<name>PREPROCESSED.pdf`, same bucket/prefix), and publishes
`PdfPreprocessingCompleted` on a *separate* stream (`OUTPUT_STREAM_NAME`) for
the next service. A CLI publishes the input event. Redis holds the dedup state
and both streams; S3 holds the PDFs.

Built from a Redis-only worker template; the messaging / tracing / health /
consumer-reliability machinery is the template's, `core/hidden_text.py` +
`core/s3.py` + the two `pdf_preprocessing_*` events and handler are this
service.

## Development Commands

```bash
make up          # docker compose up --build -d (Redis + worker)
make down
make logs        # tail the worker container
make health      # curl the worker's /health
make demo URL=<pdf-url>   # publish a request x2, watch it process once
make test        # pytest -m "not integration" — no Docker
make test-all    # + testcontainers Redis integration tests
make lint        # ruff check .
make fmt         # black . && ruff check --fix .
```

Local without Docker: `python main.py` (the worker) and
`python -m cli publish --source-uri s3://bucket/key [--job-id <id>] [--count N]`.
Redis settings default to a local instance; AWS credentials/region (standard
boto3 chain) and, for a non-AWS store, `S3_ENDPOINT_URL` must be real for the
handler to run. The credentials need write access to the source bucket.

## Architecture

1. **Messaging** (`messaging/`): Redis Streams, async.
   - `producer/redis_producer.py`: `XADD` via `get_producer()`; injects current
     trace context. `publish(envelope, *, stream=None)` — `stream` defaults to
     `STREAM_NAME`; the handler passes `OUTPUT_STREAM_NAME` explicitly.
   - `consumer/redis_consumer.py`: `RedisConsumer` — `XREADGROUP` loop, retry,
     DLQ, `XAUTOCLAIM`. Unchanged from the template.
   - `consumer/dispatcher.py`: `HANDLERS = {"PdfPreprocessingRequested": …}`.
     `PdfPreprocessingCompleted` is deliberately not registered — this worker
     publishes it but does not consume it.
   - `consumer/handlers/pdf_preprocessing_requested.py`: fetch (S3) → restore →
     upload (S3) → HSETNX guard → publish completed. Takes its own Redis client
     (`messaging/state.py`), not the consumer's.
   - `models/`: `EventEnvelope` (Literal of both event types, plus
     `traceparent`), `events/pdf_preprocessing_requested.py` (`job_id`,
     `source_uri` — validated `s3://bucket/key`),
     `events/pdf_preprocessing_completed.py` (`job_id`, `outcome`,
     `spans_restored`, `pages_affected`, `output_uri`, `completed_at`).
   - `state.py`: `get_state_client()` / `close_state_client()` — the
     handler-side Redis client, separate from the consumer's connection.

2. **Core** (`core/`):
   - `hidden_text.py`: `restore_pdf(src, dst) -> RestoreResult`. Detection =
     `get_text` with vs without `TEXT_MEDIABOX_CLIP`; spans only in the no-clip
     pass are clip-hidden. Restoration re-draws each on top, outside clips, own
     font/size/colour. Output written only when hidden text is found.
   - `s3.py`: `fetch_pdf(source_uri, dst)` / `upload_pdf(src, dest_uri)` —
     boto3, run in `asyncio.to_thread`. `HeadObject` size cap, `%PDF-` check.
     Raises `S3Error`. Process-wide client via `get_s3_client()` /
     `close_s3_client()`. Credentials/region from the standard boto3 chain;
     `S3_ENDPOINT_URL` (+ `S3_FORCE_PATH_STYLE`) point it at an S3-compatible
     store (unset = real AWS). `suffix_uri(uri, suffix)` derives the output key
     from the source (`<name>.pdf` → `<name><suffix>.pdf`).

3. **Config** (`config/`): `settings.py` (Pydantic Settings, no required
   fields), `logging.py` (structlog + OTel trace context), `tracing.py`.

Alongside: `health/server.py` (stdlib `asyncio.start_server` probe),
`cli.py` (one-shot publisher).

No API layer, no service layer, no database layer.

## Entry point

`main.py`: configures logging/tracing on import; `run_worker()` runs the
consumer + health server on one loop with SIGINT/SIGTERM handlers; graceful
shutdown waits `SHUTDOWN_TIMEOUT_SECONDS` for the in-flight message then closes
the consumer, producer and state clients.

## Configuration

`get_settings()` (`@lru_cache`). Precedence: real env var > `.env` > default.
Key settings: `REDIS_STREAM_URL`, `STREAM_NAME` (input,
`pdf.preprocessing.requests`), `CONSUMER_GROUP` (`pdf_preprocessing_v1`),
`OUTPUT_STREAM_NAME` (output, `pdf.preprocessing.completed`),
`OUTPUT_FILENAME_SUFFIX` (default `PREPROCESSED`), `S3_ENDPOINT_URL` /
`S3_FORCE_PATH_STYLE` (for a non-AWS S3-compatible store), `WORK_DIR`,
`MAX_PDF_BYTES`, `S3_*` timeouts,
`STATE_TTL_SECONDS` (TTL on `preprocessing:<job_id>` dedup keys), `HEALTH_PORT`,
`CONSUMER_*` reliability knobs, `LOG_LEVEL` / `JSON_LOGS`. AWS **credentials and
region** are not settings — boto3 reads them from env / `~/.aws` / role.

## Consumer semantics

At-least-once; handlers must be idempotent. Here that is HSETNX on
`preprocessing:<job_id>` — **placed after** the fetch+restore+upload so a
transient failure retries and re-runs the work, but before the publish so a
redelivery never emits a duplicate `PdfPreprocessingCompleted`. Output S3 key
derived from the source URI (a re-run overwrites). Handler exceptions propagate
to drive retry → DLQ. Write-then-publish gap documented in the handler docstring
(no outbox).

## Tracing

Context crosses the stream in `EventEnvelope.traceparent`. Producer injects
from the current span; consumer extracts and makes its message span current
with `start_as_current_span` — load-bearing: a detached span orphans the
`PdfPreprocessingCompleted` publish. `test_tracing.py` asserts on parent span
ids.

## Health

`health/server.py` serves only `/health` on a stdlib asyncio server. Redis
`PING` under a 2s timeout → 200 `{"status":"ok","redis":"ok"}` or 503
`{"status":"degraded","redis":"down"}`. Any other path → 404.

## Code Style

- Black, line length 88. Ruff selects E, F, W, B, I (E501 ignored).
- New non-test modules (`core/*`) use `from __future__ import annotations`.
- Import order: stdlib, third-party, local.
