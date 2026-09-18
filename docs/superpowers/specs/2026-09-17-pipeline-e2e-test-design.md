# Pipeline End-to-End Test (Conversion → Dedupe → Compression → OCR dispatch)

Date: 2026-09-17

## Goal

Prove, locally and in CI, that an uploaded record flows through the real
service binaries in the order production uses:

```
S3 upload -> File Conversion (.NET) -> DedupeServices (Python)
          -> CompressionServices (Go) -> OCRServices (Go) -> ActiveMQ queue
```

Everything runs in Docker Compose with no external credentials. The OCR stage
ends when `OCRServices` has enqueued the OCR payload on a local ActiveMQ;
`azureocrservices` and Azure Document Intelligence are out of scope.

The harness follows the shape of the existing
`MCS.FOI.S3FileConversion/docker-compose.integration.yml` +
`integration/run.sh` setup.

## Non-goals

- Running `PageCountCalculator`, `azureocrservices`, `reviewer_api` HTTP, or
  `request-management-api`. Only their side effects are simulated (DB seeds,
  nginx stubs) or asserted (messages on a stream).
- Large-file streams / workloads. Only the `normal` workload is exercised.
- Performance or redelivery/recovery behaviour (covered by the per-service
  integration suites).

## Layout

```
e2e/
  README.md
  run.sh
  docker-compose.e2e.yml
  samples/
    simple-test-doc.docx      # conversion-required path
    sample.pdf                # dedupe-ready path
  fixtures/
    nginx.conf                # record-formats stub (+ any RMA stub routes needed)
    record-formats.json
    seaweedfs/config.json
    activemq/                 # only if the image needs a custom users/queue config
  tests/
    Dockerfile
    requirements.txt
    conftest.py
    seed.py
    test_docx_pipeline.py
    test_pdf_pipeline.py
    test_duplicate.py
  TestResults/                # gitignored: compose.log, junit.xml
```

`e2e/samples/` is the only place new inputs are added; a new sample gets a
new `test_*.py` that reuses the same helpers.

## Compose services (`e2e/docker-compose.e2e.yml`)

| Service | Image / build | Purpose |
| --- | --- | --- |
| `postgres` | `postgres:18` | database `docreviewerdb`, user `foi` |
| `db-migrate` | build `api/` (existing Dockerfile) | one-shot `python manage.py db upgrade`; workers depend on it with `condition: service_completed_successfully` |
| `redis` | `redis:7` with password | all streams |
| `seaweedfs` | `chrislusf/seaweedfs:4.46` with `-s3` | S3-compatible storage; bucket names use the `-dev` suffix workers derive from `*_S3_ENV=dev` |
| `record-formats` | `nginx:1.29.1-alpine` | serves `formats.json`; extra routes added if a worker calls `request-management-api` on the happy path |
| `activemq` | `apache/activemq-classic` (pinned tag) | queue `foidococr`; Jolokia/REST enabled for the test to browse |
| `file-conversion` | build `MCS.FOI.S3FileConversion/` | consumes `e2e-conversion`, publishes `e2e-dedupe` |
| `dedupe` | build `computingservices/DedupeServices/` | consumes `e2e-dedupe`, publishes compression + `e2e-pagecount` |
| `compression` | build `computingservices/CompressionServices/` | `COMPRESSION_WORKLOAD=normal`; `COMPRESSION_MESSAGING_MODE` defaults to `legacy` (stream `e2e-compression`) and can be switched to `standard` via env; publishes `document.ocr.requested` on `foi:ocr` |
| `ocr` | build `computingservices/OCRServices/` | consumes `foi:ocr`, writes `OCRActiveMQJob`, POSTs to ActiveMQ REST |
| `e2e-tests` | build `e2e/tests/Dockerfile` | pytest runner; `--exit-code-from` target; junit XML to `/test-results` |

Stream names, DB credentials, S3 keys and ActiveMQ credentials are fixed
test-only literals in the compose file (as the conversion integration file
does); nothing is read from the root `.env`.

## Test driver (`e2e/tests/`)

Python 3.12 + pytest. Dependencies: `pytest`, `psycopg[binary]`, `redis`,
`boto3`, `requests`.

- `conftest.py`: reads settings from env, builds clients, provides
  `wait_until(predicate, timeout, interval)` and a session-scoped readiness
  check (DB reachable, consumer groups exist on the streams, ActiveMQ
  reachable).
- `seed.py`: inserts the rows `request-management-api`/`reviewer_api` would
  create before publishing (`DocumentMaster`, `DocumentAttributes`,
  `FileConversionJob` for the docx path, `DeduplicationJob` for the pdf path).
  Mirrors the seeding in
  `MCS.FOI.S3FileConversionIntegrationTests/DocxConversionEndToEndTests.cs`
  and is extended from what `DedupeServices` reads.
- Tests publish the same flat field map `request-management-api` publishes.

### Test cases

1. **docx pipeline** – upload `simple-test-doc.docx`, publish to the
   conversion stream, assert in order with a ~120 s timeout per stage:
   - `FileConversionJob` completed; converted PDF exists in S3; a message is
     on `e2e-dedupe`.
   - `DeduplicationJob` completed; hash recorded; messages on the compression
     stream and `e2e-pagecount`.
   - `CompressionJob` reached a terminal success/skipped state; compressed
     object (or original, when skipped) referenced in the job row exists in S3;
     `document.ocr.requested` present on `foi:ocr`.
   - `OCRActiveMQJob` row exists; ActiveMQ queue `foidococr` holds one message
     whose payload references the same S3 path.
2. **pdf pipeline** – upload `sample.pdf`, publish straight to `e2e-dedupe`,
   assert the dedupe → compression → OCR stages above.
3. **duplicate** – publish `sample.pdf` a second time under a new document;
   assert both `Documents` rows carry the same `DocumentHashCodes.rank1hash`.
   (Dedupe records hashes only; it always publishes compression, and duplicate
   detection happens when the reviewer reads the hashes.)

Each test uses unique IDs (ministry request, document master, job) so tests do
not interfere; the whole stack is torn down after the run.

## Runner (`e2e/run.sh`)

Same contract as `MCS.FOI.S3FileConversion/integration/run.sh`:
unique project name, `up --build --abort-on-container-exit --exit-code-from e2e-tests`,
`compose ps` + `logs` captured to `e2e/TestResults/compose.log`, logs echoed
on failure, `down --volumes --remove-orphans` always.

## Error handling

- Every wait has a timeout; on timeout the assertion message states which
  stage failed and the last observed DB/stream state.
- Worker crashes surface through `--abort-on-container-exit` and the captured
  compose log.
- Readiness is gated on healthchecks and `db-migrate` completion, not sleeps.

## Known local-only limitations

- `DedupeServices` hard-codes `https://` for its PDF metadata-cleanup upload
  (`s3documentservice.py` `_clearmetadata`). Against plain-HTTP SeaweedFS that
  step logs `metadata_cleanup` and continues; the tests do not assert on the
  `...ORIGINAL.pdf` copy.

## Open items resolved during implementation

- Whether Dedupe or Compression call `request-management-api` on the happy
  path; if so, add nginx stub routes returning the minimal JSON they expect.
- The exact ActiveMQ REST/Jolokia endpoints and auth `OCRServices` and the
  test use.
- Exact seed rows/columns required by each worker after the API migrations.

## Success criteria

`./e2e/run.sh` exits 0 with all three tests green on a clean machine with
only Docker installed, and produces `e2e/TestResults/junit.xml` and
`compose.log`.
