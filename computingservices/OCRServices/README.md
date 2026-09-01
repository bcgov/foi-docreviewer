# OCRServices

OCRServices consumes the typed `document.ocr.requested` event via
`github.com/bcgov/foi-messaging-go`, pushes each document to ActiveMQ over HTTP,
and records idempotent job outcomes in PostgreSQL.

## Messaging

| Topic | Stream | Consumer group |
| --- | --- | --- |
| `ocr` | `foi:ocr` | `foi-ocr` |

Delivery is at-least-once; the handler is idempotent on `ocractivemqjobid`.
Transient failures (ActiveMQ/DB unavailable) are retried with backoff and
reclaimed; malformed envelopes and rejected (4xx) pushes are dead-lettered to
`foi:ocr.dlq`.

## Configuration

Start from [`sample.env`](sample.env). The stream prefix must be `foi` and the
topic `ocr`. `MESSAGING_CLAIM_MIN_IDLE` must exceed `OCR_PROCESSING_TIMEOUT`.

## Coordinated cutover from the legacy flat stream

1. Stop new work landing on the old `OCR_STREAM_KEY` flat stream and let the
   previous consumer drain it to empty.
2. Deploy CompressionServices (publishing typed OCR events to `foi:ocr`) and
   OCRServices (consuming `foi:ocr` as group `foi-ocr`) together.
3. Retire the old `OCR_STREAM_KEY` and any `<consumer>:lastid` checkpoint keys.

## Local development

```bash
cd computingservices/OCRServices
cp sample.env .env  # fill in local values
set -a; . ./.env; set +a
go mod download
go run .
```

## Testing

```bash
go test ./...
go test -race ./...
go vet ./...
go mod tidy -diff
```
