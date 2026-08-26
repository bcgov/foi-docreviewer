# CompressionServices

CompressionServices consumes compression requests, processes documents with a
bounded file-based pipeline, persists idempotent job outcomes in PostgreSQL,
and optionally publishes OCR follow-up work. It supports both the hardened
legacy Redis-stream contract and the typed standard contract used by
`github.com/bcgov/foi-messaging-go`.

## Runtime commands

The binary reads configuration from environment variables and handles graceful
shutdown on `SIGINT` and `SIGTERM`.

```bash
# Consume using the configured legacy or standard mode (the default command).
./compression-service

# Explicit equivalent of the default command.
./compression-service consume

# Run one bounded stale-job reconciliation pass and exit.
./compression-service reconcile
```

Unknown commands fail before Redis or PostgreSQL connections are opened. The
reconciler uses the same PostgreSQL advisory lock as normal processing and
records `stale_unfinished` for jobs that remain stale and unfinished.

## Messaging modes

### Legacy mode

Legacy mode reads flat Redis stream fields from `COMPRESSION_STREAM_KEY` and
stores progress in `COMPRESSION_CHECKPOINT_KEY`. Messages are processed one at
a time. The checkpoint advances only after the shared handler succeeds;
retryable failures retain the current entry and use bounded exponential
backoff.

### Standard mode

Standard mode uses `foi-messaging-go v0.1.0` and a typed compression event.
Workloads are isolated by topic:

| Workload | Topic | Default group |
| --- | --- | --- |
| `normal` | `foi:compression` | `foi-compression-normal` |
| `large` | `foi:compression-large` | `foi-compression-large` |

The adapter owns registration, acknowledgement/NACK, delivery caps, pending
entry reclaim, and Redis client lifecycle. CompressionServices does not
dual-publish standard and legacy messages.

## Configuration

Start with [`sample.env`](sample.env). Required runtime groups are:

| Variables | Purpose |
| --- | --- |
| `COMPRESSION_MESSAGING_MODE`, `COMPRESSION_WORKLOAD` | Select legacy/standard mode and normal/large workload. |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` | Redis connection. |
| `COMPRESSION_DB_HOST`, `COMPRESSION_DB_PORT`, `COMPRESSION_DB_NAME`, `COMPRESSION_DB_USER`, `COMPRESSION_DB_PASSWORD` | PostgreSQL connection. |
| `COMPRESSION_S3_HOST`, `COMPRESSION_S3_REGION`, `COMPRESSION_S3_SERVICE`, `COMPRESSION_S3_ENV` | S3-compatible object storage. |
| `COMPRESSION_PROCESSING_TIMEOUT` | Absolute processing budget; defaults to 15 minutes for normal and 60 minutes for large workloads. |
| `MESSAGING_CLAIM_INTERVAL`, `MESSAGING_CLAIM_MIN_IDLE` | Standard consumer reclaim timing. Claim idle must exceed processing timeout. |
| `MESSAGING_MAX_DELIVERY_ATTEMPTS`, `MESSAGING_SHUTDOWN_TIMEOUT` | Delivery cap and graceful shutdown budget. |
| `COMPRESSION_RATIO_THRESHOLD` | Compression ratio threshold; must be finite and in `(0,1]`. |
| `COMPRESSION_S3_PRESIGN_EXPIRY` | Presigned URL lifetime; maximum 15 minutes. |
| `COMPRESSION_RECONCILIATION_NORMAL_AFTER`, `COMPRESSION_RECONCILIATION_LARGE_AFTER`, `COMPRESSION_RECONCILIATION_UNKNOWN_AFTER`, `COMPRESSION_RECONCILIATION_BATCH_SIZE` | Reconciliation age thresholds and batch size. |

Standard mode additionally requires `MESSAGING_STREAM_PREFIX`,
`COMPRESSION_TOPIC`, and `MESSAGING_CONSUMER_GROUP`. The prefix is `foi` and
the topic must match the selected workload. Legacy mode requires the stream
and checkpoint keys instead.

The loader validates cross-setting relationships before opening external
connections. Credentials, payloads, presigned URLs, filenames, document paths,
and tool diagnostics are not returned in operational error text or logs.

## Local development

```bash
cd computingservices/CompressionServices
cp sample.env .env  # fill in local values
set -a; . ./.env; set +a
go mod download
go run . consume
```

For the repository Compose workflow, set the variables from the root
[`sample.env`](../../sample.env) and start the compression service through
`docker-compose.yml`.

The container image installs Ghostscript and runs the compiled binary. The
application owns one PostgreSQL pool, one timed HTTP client, and the selected
Redis consumer lifecycle.

## Testing

Run the module tests and static checks from the service directory:

```bash
go test ./...
go test -race ./...
go vet ./...
go mod verify
go mod tidy -diff
```

Deployment configuration tests live in the DedupeServices test suite:

```bash
cd ../DedupeServices
pytest unittests/testcompressiondeploymentconfiguration.py -q
```

Some HTTP tests use `httptest.NewServer`; environments that restrict loopback
listeners may need to run the race suite in a container or an unrestricted CI
runner.

## Reliability model

- PostgreSQL advisory locks serialize work per compression job.
- Versioned job writes are idempotent and terminal outcomes are conflict-safe.
- Legacy checkpoints advance only after successful processing.
- Standard deliveries are retried and reclaimed by the messaging library.
- Stale version-1/version-2 jobs are reconciled without replaying payloads.
- Terminal OCR/redaction follow-up is best effort and cannot overwrite a
  confirmed compression outcome.
- Structured logs contain safe categories and approved identifiers only.

## Rollout

Deploy legacy mode during the rollback window, verify reconciliation and job
state, then deploy standard consumers against empty standard topics. Switch the
normal workload first, followed by large files. Keep legacy stream/checkpoint
configuration until the rollback window is explicitly closed.
