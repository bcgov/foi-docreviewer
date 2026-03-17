# Zipping Process

## Purpose

This document describes the current zipping flow used by the redline and final-package endpoints.

It covers the active pipeline:

1. API accepts the package request.
2. Document service optionally generates summary PDFs.
3. Document service forwards the package payload to the zipper stream.
4. Zipping service downloads all source files from object storage, creates the ZIP, uploads the final archive, records package/job state, and emits completion notifications.

This document intentionally focuses on the current `DocumentServices` -> `ZippingServices` path, not the older `PDFStitchServices` zipper producer flow.

## End-to-End Flow

1. The API receives `POST /api/triggerdownloadredline` or `POST /api/triggerdownloadfinalpackage`.
2. The API creates a `PDFStitchJob` row and publishes a document-service stream message.
3. `DocumentServices` consumes the message.
4. `redactionsummaryservice` generates zero or more summary PDFs, depending on category.
5. `DocumentServices` merges the original `filestozip` with any generated summary files.
6. `DocumentServices` publishes the merged payload to the zipper Redis stream.
7. `ZippingServices` consumes the zipper message.
8. `ZippingServices` downloads each file referenced in `filestozip`.
9. `ZippingServices` writes each file into a ZIP archive.
10. The completed ZIP is uploaded to object storage.
11. The final ZIP path is written to `PDFStitchPackage`.
12. Completion or error notifications are emitted for redline and response-package flows.

## Entry Points

### API and document-service handoff

- [radactionservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/services/radactionservice.py#L125) prepares the initial package message and flattens `attributes[*].files[*]` into `filestozip`.
- [documentservicestreamreader.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/rstreamio/reader/documentservicestreamreader.py#L66) consumes the document-service stream message.
- [zippingservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/zippingservice.py#L6) appends summary files and forwards the message to the zipper stream.
- [zipperstreamwriter.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/rstreamio/writer/zipperstreamwriter.py#L5) writes the final zipper message.

### Zipper consumer and worker

- [foirediszipperconsumer.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/foirediszipperconsumer.py#L24) reads the zipper Redis stream.
- [zipperservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/zipperservice.py#L16) performs the actual ZIP creation and upload.
- [zipperdboperations.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/zipperdboperations.py#L6) records job status and final package location.
- [notificationservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/notificationservice.py#L8) publishes completion notifications.

## Message Contract

The active zipper payload is represented by [zipperproducermessage.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/models/zipperproducermessage.py#L1).

Important fields:

| Field | Description |
| --- | --- |
| `jobid` | Primary job identifier used across `PDFStitchJob` versions. |
| `category` | Determines package type, DB category normalization, and notification behavior. |
| `requestnumber` | Used to build the final ZIP file path. |
| `bcgovcode` | Used to resolve object-storage credentials and target bucket. |
| `createdby` | Persisted in job/package rows and notifications. |
| `ministryrequestid` | Request identifier used in DB writes and notifications. |
| `filestozip` | JSON array of files to fetch and add to the ZIP. |
| `attributes` | Original package metadata, persisted into job records. |
| `feeoverridereason` | Forwarded to response-package notifications. |
| `foldername` | Optional top-level folder name that overrides the default category-based ZIP path. |
| `phase` | Used to normalize phase categories when saving final package records. |

### `filestozip` shape

`filestozip` is a JSON string containing objects like:

```json
[
  {
    "filename": "Minister of State/ECC-4535-455 - redline - Minister of State.pdf",
    "s3uripath": "https://.../ECC-4535-455/redline/Minister of State/ECC-4535-455 - redline - Minister of State.pdf"
  },
  {
    "filename": "Minister of State/ECC-4535-455 - Redline - summary.pdf",
    "s3uripath": "https://.../ECC-4535-455/redline/Minister of State/ECC-4535-455 - Redline - summary.pdf"
  }
]
```

`filename` becomes the internal ZIP entry path. If it includes path separators, the resulting ZIP preserves that folder structure.

## How Files Reach the Zipper

The zipper never assembles source files itself. It consumes a prepared file list.

### Original package files

The API builds `filestozip` by flattening `attributes[*].files[*]`.

Reference: [radactionservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/services/radactionservice.py#L174)

### Summary files

If summary generation runs successfully, `DocumentServices` appends the generated summary files to the original `filestozip` before publishing to the zipper stream.

Reference: [DocumentServices zippingservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/zippingservice.py#L11)

That means the zipper operates on the final complete file list:

- Stitched package PDFs already uploaded to object storage.
- Generated summary PDFs, when applicable.

## Stream Consumption Model

`foirediszipperconsumer.py` uses a simple stream-reader model:

- Reads from the configured zipper stream.
- Tracks the last processed message ID per consumer in Redis.
- Decodes each message from bytes to strings.
- Converts the JSON payload into a `zipperproducermessage`.
- Calls `processmessage(...)`.
- Calls `sendnotification(...)` after processing.
- Deletes the stream message after handling it.

Reference: [foirediszipperconsumer.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/foirediszipperconsumer.py#L24)

This consumer does not use Redis consumer groups; it persists a last-seen stream ID instead.

## ZIP Creation Logic

The active ZIP creation logic lives in [zipperservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/zipperservice.py#L16).

### Processing stages

1. Resolve S3 credentials from `bcgovcode`.
2. Record zipper job start in `PDFStitchJob` with status `zippingstarted`.
3. Parse `filestozip`.
4. Download each source file from object storage.
5. For PDFs, rebuild the document through `PyPDF2` to strip metadata and other sensitive content.
6. Write each file into a temporary ZIP archive using `ZIP_DEFLATED` with `compresslevel=9`.
7. Upload the final ZIP to object storage.
8. Record zipper completion in `PDFStitchJob`.
9. Save the final uploaded path in `PDFStitchPackage`.
10. Record final job completion or error state.

### PDF sanitization

For `.pdf` sources, the zipper runs the bytes through `__removesensitivecontent(...)`, which:

- Reads the PDF with `PyPDF2.PdfReader`
- Copies pages into a new `PdfWriter`
- Writes a new PDF byte stream without preserving metadata

If sanitization fails for a file, the service logs the exception and falls back to the original file bytes for that ZIP entry.

Reference: [zipperservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/zipperservice.py#L91)

## Object Storage Reads and Writes

The zipper service fetches both source files and upload credentials dynamically.

### Credential lookup

`getcredentialsbybcgovcode(...)` queries `DocumentPathMapper` for the bucket `{bcgovcode}-{env}-e` and category `Records`.

Reference: [s3documentservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/s3documentservice.py#L10)

### Source-file download

Each `s3uripath` in `filestozip` is fetched with an AWS-signed `GET` request.

Reference: [s3documentservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/s3documentservice.py#L28)

### ZIP upload

The final ZIP is uploaded to:

```text
https://{s3_host}/{bcgovcode}-{env}-e/{requestnumber}/{zip-path}
```

Reference: [s3documentservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/s3documentservice.py#L50)

## Final ZIP Naming

ZIP naming is handled by `__getzipfilepath(...)` in [zipperservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/zipperservice.py#L178).

Rules:

- If `foldername` is set, ZIP path is `{FoldernameCapitalized}/{requestnumber}.zip`
- Otherwise, ZIP path is `{CategoryCapitalized}/{requestnumber}.zip`

Examples:

- `Redline/ECC-4535-455.zip`
- `Responsepackage/ECC-4535-455.zip`

The uploaded object key always sits under `{requestnumber}/...` in the target bucket.

## Database Writes

The zipper process writes to two main tables.

### `PDFStitchJob`

`recordjobstatus(...)` inserts new versions of the same `pdfstitchjobid`.

For zipper processing, categories are normalized as:

- `redline-zipper`
- `responsepackage-zipper`
- `oipcredline-zipper`
- `openinfo-zipper`
- Phase categories collapse to `redline-zipper` or `responsepackage-zipper`

Observed statuses:

- `zippingstarted` at version `3`
- `zippingcompleted` at version `4`
- `completed` or `error` at version `5`

Reference: [zipperdboperations.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/zipperdboperations.py#L26)

### `PDFStitchPackage`

After a successful upload, `savefinaldocumentpath(...)` stores:

- `ministryrequestid`
- normalized `category`
- final ZIP `documentpath`
- `createdby`

Reference: [zipperdboperations.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/zipperdboperations.py#L6)

## Category Normalization

Two separate normalization rules matter in the zipper flow.

### Job-status normalization

`assigncategory(...)` collapses phase variants:

- any `redline_phase...` becomes `redline`
- any `responsepackage_phase...` becomes `responsepackage`

This affects `PDFStitchJob` category values.

### Final-package normalization

Before saving `PDFStitchPackage`, `zipperservice.processmessage(...)` removes underscores from phase categories:

- `redline_phase2` becomes `redlinephase2`
- `responsepackage_phase1` becomes `responsepackagephase1`

Reference: [zipperservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/zipperservice.py#L35)

## Notifications

After processing, the consumer calls `sendnotification(...)`.

### Redline and response package

For these categories, notifications are emitted only after zipper completion has been confirmed through `isredlineresponsezipjobcompleted(...)`.

Service IDs:

- `pdfstitchforredline`
- `pdfstitchforresponsepackage`

For response-package notifications, `feeoverridereason` is included when present.

Reference: [notificationservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/notificationservice.py#L24)

### Harms

The zipper service also supports harms notifications, but that is a different package flow and not the primary path used by the current redline/final-package endpoints.

## Error Handling

The zipper worker records errors at the job layer and does not silently ignore failures.

Important behavior:

- Any top-level exception in `processmessage(...)` results in version `5` status `error`.
- Upload failure also results in final `error` status.
- Individual PDF metadata-scrubbing failures do not fail the whole ZIP; the original bytes are used instead.
- S3 `GET` and `PUT` operations retry according to configured retry counts in the zipper service config.

## Operational Characteristics

- The ZIP is built in a temporary spooled file, not streamed directly from source to destination.
- Compression uses `ZIP_DEFLATED` with `compresslevel=9`.
- `allowZip64=True` is enabled, so large ZIPs are supported.
- The zipper expects every `filestozip[*].s3uripath` object to already exist and be readable with the resolved ministry credentials.
- Internal ZIP structure is entirely controlled by `filestozip[*].filename`.

## Practical Example

For a redline request:

1. The API produces `filestozip` from redline PDF paths uploaded by the frontend.
2. The document service adds `... - summary.pdf` files.
3. The zipper downloads each referenced PDF.
4. The zipper creates `Redline/{requestnumber}.zip`.
5. The zipper uploads the archive to object storage under `{requestnumber}/Redline/{requestnumber}.zip`.
6. The final path is persisted in `PDFStitchPackage`.
7. A `pdfstitchforredline` notification is emitted.
