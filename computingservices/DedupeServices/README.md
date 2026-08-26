# DedupeServices

DedupeServices identifies duplicate documents, records dedupe outcomes, and
publishes compression and page-calculator work for the FOI document-review
pipeline. It is a Python service with Redis stream integrations, PostgreSQL
persistence, S3-compatible storage, and structured JSON logging.

## Running the service

The container entrypoint executes `__main__.py`, which configures logging and
starts the Redis-backed dedupe consumer.

```bash
cd computingservices/DedupeServices
python __main__.py
```

The service expects its runtime settings as environment variables. Start with
[`.sampleenv`](.sampleenv), or use the repository-level [`sample.env`](../../sample.env)
for the local Compose configuration.

## Configuration

| Variables | Purpose |
| --- | --- |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` | Redis connection used by dedupe and stream publishers. |
| `DEDUPE_STREAM_KEY` | Input dedupe stream. |
| `DEDUPE_DB_HOST`, `DEDUPE_DB_PORT`, `DEDUPE_DB_NAME`, `DEDUPE_DB_USER`, `DEDUPE_DB_PASSWORD` | PostgreSQL connection. |
| `DEDUPE_S3_HOST`, `DEDUPE_S3_REGION`, `DEDUPE_S3_SERVICE`, `DEDUPE_S3_ENV` | S3-compatible document storage. |
| `PAGECALCULATOR_STREAM_KEY` | Page-calculator output stream. |
| `HEALTH_CHECK_INTERVAL` | Health and liveness check interval. |

Compression publishing is selected independently through:

| Variable | Values / behavior |
| --- | --- |
| `COMPRESSION_MESSAGING_MODE` | `legacy` or `standard`; deployments default to `legacy` during rollout. |
| `COMPRESSION_WORKLOAD` | `normal` or `large`. |
| `MESSAGING_STREAM_PREFIX` | Standard contract prefix; deployments use `foi`. |
| `COMPRESSION_TOPIC` | `compression` for normal or `compression-large` for large files. |
| `COMPRESSION_STREAM_KEY` | Legacy compression stream retained for rollback. |
| `COMPRESSION_CHECKPOINT_KEY` | Stable legacy consumer checkpoint identity. |

The producer does not dual-publish. Standard events use the typed envelope
consumed by `github.com/bcgov/foi-messaging-go v0.1.0`; legacy mode preserves
the existing flat Redis field representation.

## Compression event contract

The standard publisher writes one event per compression request to the
workload-specific topic:

| Workload | Topic |
| --- | --- |
| Normal | `foi:compression` |
| Large | `foi:compression-large` |

Payloads are JSON-native and include stable event and correlation identifiers,
UTC timestamps, the compression message fields, and the selected workload.
Required fields and types are validated before publication. Values are rejected
rather than silently coerced.

## Local development

```bash
cd computingservices/DedupeServices
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python __main__.py
```

For the full local stack, configure the root `.env` and start the Dedupe
container through `docker-compose.yml`. Do not place real passwords, access
tokens, or presigned URLs in sample files or logs.

## Testing

Run the fast unit suite from this directory:

```bash
pytest -q
```

Target the messaging and deployment contracts directly when iterating:

```bash
pytest -q \
  unittests/testcompressionevents.py \
  unittests/testcompressionproducermessage.py \
  unittests/testcompressionproducerservice.py \
  unittests/testdeploymentconfiguration.py \
  unittests/testcompressiondeploymentconfiguration.py
```

The Redis/Go compatibility test is opt-in because it starts Docker and builds
the pinned Go consumer fixture:

```bash
RUN_COMPRESSION_CONTRACT_TESTS=1 \
  pytest -q integrationtests/test_go_compression_contract.py
```

The integration fixture uses Redis 7 on `127.0.0.1:16379`, publishes to both
standard workload topics, and verifies topic isolation and cross-language
envelope compatibility.

## Observability and safety

Logging is configured through `utils.loggingutils` and emits structured JSON.
Operational logs may include safe event, stream, job, and document identifiers,
but must not include payloads, document contents, S3 paths, credentials, or
user tokens. Compression and page-calculator publication failures retain their
original exception context for handling while exposing safe operational fields.

## Rollout guidance

1. Deploy the producer changes with `legacy` mode and verify stream health.
2. Keep normal and large workloads on distinct topic/stream settings.
3. Deploy and verify hardened CompressionServices consumers and reconciliation.
4. Start standard consumers against empty standard topics.
5. Switch normal workload publishing first, then large-file publishing.
6. Retain legacy stream and checkpoint settings until the rollback window is
   explicitly closed.

Rollback changes only the affected workload to legacy mode. Standard topics and
consumer groups remain available for inspection; standard messages are not
copied into legacy streams.
