# Contributing to PDF Preprocessing

This service consumes `PdfPreprocessingRequested` events, restores
clip-hidden text in PDFs, stores a restored copy beside the source object, and
publishes `PdfPreprocessingCompleted` for the next service in the FOI pipeline.
Changes should preserve that contract unless the downstream consumers and their
owners are changed in the same delivery.

## Local setup

Prerequisites: Python 3.14, Poetry, Docker Compose, and AWS CLI v2.

```bash
poetry install
make up

# The demo publishes an event; upload its source PDF first.
AWS_ACCESS_KEY_ID=dev AWS_SECRET_ACCESS_KEY=dev AWS_DEFAULT_REGION=us-east-1 \
  aws --endpoint-url http://localhost:8333 \
  s3 cp ./doc.pdf s3://pdf-preprocessing/incoming/doc.pdf

make health
make demo SOURCE_URI=s3://pdf-preprocessing/incoming/doc.pdf
```

Local Compose starts Redis, SeaweedFS, and the worker. `make up` also runs the
idempotent bucket initializer for `pdf-preprocessing`. See [README.md](README.md)
for output inspection and dead-letter troubleshooting.

## Before opening a pull request

```bash
make fmt
make lint
make test
make test-all
docker compose --profile init config
```

Run `make test-all` for changes to Redis Streams behavior, S3 access, tracing,
or worker lifecycle. For a local end-to-end change, upload a real PDF and run
the demo flow above; confirm the expected output object and completion event.

## Project rules

- Keep source and restored objects in the same bucket and prefix. The default
  naming contract is `<name>.pdf` → `<name>PREPROCESSED.pdf`.
- Preserve at-least-once delivery handling. A handler must be idempotent and
  must return before publishing when its idempotency guard has already won.
- Do not publish a consumed event back to its input stream. This worker reads
  `pdf.preprocessing.requests` and publishes to
  `pdf.preprocessing.completed`.
- Keep boto3 work off the asyncio event loop. S3 calls belong behind the
  thread-backed helpers in `core/s3.py`.
- Treat object validation as a security boundary: retain the size cap and PDF
  header check unless their replacements provide equivalent protection.
- Keep secrets out of source control. Local Compose uses `dev` / `dev` only
  for SeaweedFS; production credentials come from the deployment environment.

## Adding or changing events

1. Define or update the payload under `messaging/models/events/`.
2. Update the event `Literal` and `EventPayload` union in
   `messaging/models/envelope.py`.
3. Add or update a handler in `messaging/consumer/handlers/`.
4. Register a consumed event in `messaging/consumer/dispatcher.py`.
5. Add unit tests and integration coverage for routing, retries, idempotency,
   and the emitted event where applicable.

If you touch publishing or consumption, preserve W3C trace context:
producers inject it into the envelope and consumers must use
`start_as_current_span` so downstream events remain children of the consumed
message span.

## Code and documentation

- Format with Black and lint with Ruff; use `make fmt` and `make lint`.
- Prefer clear names over comments that restate code. Add comments or docstrings
  for non-obvious ordering, failure windows, or operational constraints.
- Update [README.md](README.md) when local workflow, object flow, endpoints,
  or operational commands change.
- Update [BEST_PRACTICES.md](BEST_PRACTICES.md) when an architectural,
  reliability, security, tracing, or testing practice changes.
- Keep commits scoped and use the existing Conventional Commit-style prefixes,
  such as `feat:`, `fix:`, `docs:`, or `test:`.
