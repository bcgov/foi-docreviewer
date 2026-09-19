# Azure OCR worker end-to-end test

Runs the real `computingservices/azureocrservices` worker and `azuredococrapi` in
Docker Compose against ActiveMQ, SeaweedFS (S3) and Postgres. Azure Document
Intelligence is replaced by `mock-azure/`, a Flask service the tests steer.

```
test → S3 upload + DB seed → ActiveMQ foidococr
worker → download → mock :analyze → poll → /pdf → S3 <name>OCR.pdf → azuredococrapi → DB
test → DocumentOCRJob chain, DocumentMaster.ocrfilepath, S3 object, mock /_stats
```

## Run

```bash
./e2e-ocr/run.sh                      # whole suite (~15 min; the worker is sequential)
./e2e-ocr/run.sh test_ocr_happy_path.py -v
```

Requires Docker with Compose v2. The first run builds four images (api for
migrations, azuredococrapi, mock-azure, azure-ocr-worker). Results land in
`e2e-ocr/TestResults/`: `junit.xml`, `compose.log`, `e2e-tests.log` and the
worker's `worker-*dococrlog.txt`.

## What is asserted

| Test file | Evidence |
| --- | --- |
| `test_readiness.py` | tables, S3, ActiveMQ REST, mock `/healthz`, status API 403 without secret, worker wrote a log |
| `test_ocr_happy_path.py` | `azureocrrequestcreated → ocrjobrunning → ocrjobsucceeded`; `DocumentMaster.ocrfilepath` + `isredactionready`; `DocumentAttributes.ocrfilesize`; `<name>OCR.pdf` equals the mock output; compressed path preferred |
| `test_ocr_batch.py` | 10 documents complete; `max_concurrent_analyze <= E2E_OCR_MAX_CONCURRENT`; one `ocrjobrunning` per document (**xfail** today) |
| `test_ocr_throttling.py` | 429 on submit / poll / result (**xfail** today), analyze concurrency cap |
| `test_ocr_failures.py` | Azure `failed` → `ocrjobfailed`, no file, neighbour completes; missing source (**xfail** today) |

`xfail(strict=True)` marks behaviour the current worker does not have (see
`docs/azure-ocr-batch-throttling-findings.md`). When the worker is fixed the
test XPASSes, the run fails, and the marker must be removed. To see *why* each
one fails today: `./e2e-ocr/run.sh test_ocr_throttling.py -v --runxfail`.

## Mock Azure

`POST /_control` sets a scenario (`processing_polls`, `submit_429_first`,
`poll_429_first`, `result_429_first`, `retry_after_seconds`,
`max_concurrent_analyze`, `fail_ops_matching`, `submit_latency_ms`), `DELETE
/_control` resets, `GET /_stats` returns request counts, 429s served, max
concurrent Analyze calls, analyze timestamps and per-operation state. The
mock returns the submitted bytes as the "searchable" PDF, so a test can prove
the object in S3 came from the document it seeded. Unit tests:
`cd e2e-ocr/mock-azure && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pytest`.

## Notes

- The worker reads its config through `viper.AutomaticEnv()`, which upper-cases
  the key before `os.LookupEnv`. The lowercase names in
  `computingservices/azureocrservices/sample.env` only work via a `.env` file;
  the compose file sets them as `S3ENDPOINT`, `ACTIVEMQBASEURL`, `LOGFILEPATH`, …
- `ocrfileuploadsuccess` does not create a `DocumentOCRJob` row: `azuredococrapi`
  updates `DocumentMaster`/`DocumentAttributes` instead, so "done" is
  `DocumentMaster.ocrfilepath IS NOT NULL`.
- The worker's `ACTIVEMQBASEURL` carries `readTimeout=1000` so the empty
  long-poll that ends each run is short; the code appends
  `://<queue>&clientId=<id>`, so the URL must end with `destination=queue`.
- The producer publishes lowercase JSON keys; the worker's struct uses
  `documentId`/`S3FilePath` and relies on Go's case-insensitive matching. The
  tests publish the producer's form.
- `Documents` rows are seeded with `statusid = 1` and `created_at = now()`, the
  same values `DedupeServices` writes; both columns are NOT NULL in the schema.
