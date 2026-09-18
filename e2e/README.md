# Pipeline end-to-end test

Runs the real service binaries in Docker Compose and pushes sample files through

```
S3 upload -> File Conversion (.NET) -> DedupeServices -> CompressionServices -> OCRServices -> ActiveMQ
```

`azureocrservices` and Azure Document Intelligence are not run; the test ends
when `OCRServices` has enqueued the OCR payload on the local ActiveMQ queue.

## Run

```bash
./e2e/run.sh                                   # legacy compression stream (default)
COMPRESSION_MESSAGING_MODE=standard E2E_COMPRESSION_STREAM=foi:compression ./e2e/run.sh  # typed foi:compression envelope
```

Requires Docker with Compose v2. The first run builds five images (api for
migrations, conversion, dedupe, compression, ocr) and takes several minutes.
`run.sh` runs `docker compose run --rm --build e2e-tests`, and results land in
`e2e/TestResults/`: `junit.xml`, `compose.log` (all container output; echoed
to stderr on failure) and `e2e-tests.log` (a live tee of the pytest output).

## What is asserted

| Stage | Evidence |
| --- | --- |
| Conversion (docx, msg) | `FileConversionJob` v3 `completed`; converted PDF in S3; message on `e2e-dedupe`; msg attachments get `DocumentMaster` rows under `parentid` and their own completed `FileConversionJob` |
| Dedupe | `DeduplicationJob` v3 `completed`; `Documents` + `DocumentHashCodes` rows; messages on the compression and `e2e-pagecount` streams |
| Compression | `CompressionJob` v3 `completed`/`skipped`; `DocumentMaster.compressedfilepath` object exists; `document.ocr.requested` on `foi:ocr` |
| OCR dispatch | `OCRActiveMQJob` v3 `completed`; payload consumed from ActiveMQ queue `foidococr` references the document |

Tests: `tests/test_pdf_pipeline.py`, `tests/test_docx_pipeline.py`, `tests/test_msg_pipeline.py`,
`tests/test_duplicate.py`; a session-wide autouse fixture in `conftest.py`
blocks every test until File Conversion, Dedupe and OCR have all registered
their consumer groups, so a pipeline test never races a worker that hasn't
started yet. `tests/test_readiness.py` re-checks the same conditions with
per-component diagnostics if something is still broken.

## Adding a sample

1. Drop the file in `samples/`.
2. Copy `tests/test_pdf_pipeline.py` (dedupe-ready formats) or
   `tests/test_docx_pipeline.py` (conversion formats), change `FILENAME`,
   content type and the `seed.new_ids(prefix=...)` value to an unused prefix.
3. If the extension is new, add it to `fixtures/record-formats.json`.

`samples/msg-with-attachments.msg` is synthetic; regenerate it with
`samples/msggen` (see its README) rather than replacing it with a real email.

## Layout

- `docker-compose.e2e.yml` – all services; credentials are test-only literals
- `run.sh` – wrapper around `docker compose run --rm --build e2e-tests` with log capture
- `fixtures/` – nginx record-formats stub, SeaweedFS identities
- `tests/` – pytest runner (`settings.py`, `clients.py`, `seed.py`, `stages.py`)

## Known local-only behaviour

- DedupeServices hard-codes `https://` for its PDF metadata-cleanup upload; against
  plain-HTTP SeaweedFS it logs `metadata_cleanup` and continues. Nothing asserts
  on the `...ORIGINAL.pdf` copy.
- The api migrations pre-seed `DocumentPathMapper` for `citz-dev-e` with NULL
  attributes, so `seed.ensure_path_mapper` also UPDATEs that row with the dev
  S3 keys.
- `foi:ocr` entries carry a binary msgpack `metadata` field (Watermill), so
  `clients.Redis.entries` reads via a raw connection and drops non-UTF-8
  fields.
