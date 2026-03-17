# Summary Generation

## Purpose

This document describes how summary PDFs are generated for redline and response-package downloads in FOI Doc Reviewer.

The summary generator is not executed inside the API request thread. The API accepts a package request, persists job state, publishes a stream message, and the downstream document service creates the summary PDF asynchronously before handing the package off to the zipper service.

## End-to-End Flow

1. The frontend prepares `summarydocuments` and package metadata.
2. The API receives `POST /api/triggerdownloadredline` or `POST /api/triggerdownloadfinalpackage`.
3. The API stores a `PDFStitchJob` row with status `pushedtostream`.
4. The API publishes a message to the document-service Redis stream.
5. `documentservicestreamreader` consumes the message.
6. `redactionsummaryservice` generates one or more summary PDFs unless the category suppresses summary generation.
7. Generated summary PDFs are uploaded to object storage.
8. The original package files plus the generated summary PDFs are forwarded to the zipper stream.

## Entry Points

### API layer

- [redaction.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/resources/redaction.py#L305) accepts redline package requests.
- [redaction.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/resources/redaction.py#L332) accepts final package requests.
- [radactionservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/services/radactionservice.py#L125) creates the job record and publishes the stream message.

### Document service layer

- [documentservicestreamreader.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/rstreamio/reader/documentservicestreamreader.py#L60) consumes the stream message.
- [redactionsummaryservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/redactionsummaryservice.py#L13) orchestrates summary generation.
- [redactionsummary.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/dts/redactionsummary.py#L7) builds the summary data model.
- [documentgenerationservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/documentgenerationservice.py#L30) renders the PDF via CDOGS.
- [zippingservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/zippingservice.py#L6) appends generated summaries to `filestozip` and forwards the package.

## Input Contract

Summary generation depends on the stream payload produced by the API. The key fields are:

| Field | Description |
| --- | --- |
| `category` | Determines summary template, page-flag behavior, and file naming. |
| `requestnumber` | Used in the summary file name and rendered content. |
| `bcgovcode` | Enables ministry-specific behavior such as MCF personal request handling. |
| `attributes` | Carries division/package metadata and points at the stitched package PDFs already uploaded to object storage. |
| `summarydocuments.sorteddocuments` | Canonical document order used to calculate stitched page ranges. |
| `summarydocuments.pkgdocuments` | Package grouping. For redline this is usually per division; for response package it is typically a single package entry. |
| `redactionlayerid` | Determines which redaction layer is queried for sections and page flags. |
| `requesttype` | Used for special-case logic, especially `mcf` + `personal`. |
| `phase` | Restricts summary content for phased redline and phased response-package categories. |
| `documentsetid` | Enables record-group expansion before summary generation. |

## Where `summarydocuments` Comes From

The frontend builds `summarydocuments` before calling the package endpoints.

### Redline flow

For redline packages, the frontend groups document IDs by division and also creates a globally ordered `sorteddocuments` list.

Reference: [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js#L1044)

Typical shape:

```json
{
  "sorteddocuments": [26586, 26587, 26590],
  "pkgdocuments": [
    { "divisionid": 87, "documentids": [26586, 26587] },
    { "divisionid": 92, "documentids": [26590] }
  ]
}
```

### Response package flow

For response packages, the frontend usually builds a single package entry with `divisionid = 0`.

Reference: [useSaveResponsePackage.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveResponsePackage.js#L143)

Typical shape:

```json
{
  "sorteddocuments": [301, 302, 303],
  "pkgdocuments": [
    { "divisionid": 0, "documentids": [301, 302, 303] }
  ]
}
```

### MCF personal request variant

For `bcgovcode = "mcf"` and `requesttype = "personal"`, response-package summaries use record-level groupings instead of a flat document list. Each record carries a generated `recordname` and its own `documentids`.

Typical shape:

```json
{
  "sorteddocuments": [301, 302, 303],
  "pkgdocuments": [
    {
      "divisionid": 0,
      "documentids": [301, 302, 303],
      "records": [
        { "recordname": "APPLICANT - MEDICAL - T123", "documentids": [301, 302] },
        { "recordname": "MEDICAL - T124", "documentids": [303] }
      ]
    }
  ]
}
```

## Category Behavior

### Categories that generate summaries

- `redline`
- `redline_phase{n}`
- `responsepackage`
- `responsepackage_phase{n}`
- `oipcreviewredline`
- `oipcredline`
- `openinfo`

### Category that skips summary generation

- `consultpackage`

`consultpackage` returns no summary files and goes directly to the zipper flow.

## Template Selection

The document service chooses a CDOGS template based on category and request type.

| Condition | Template |
| --- | --- |
| `bcgovcode == "mcf"` and `requesttype == "personal"` and response-package/openinfo flow | `CFD_responsepackage_redaction_summary` |
| `category` contains `responsepackage` or equals `openinfo` | `responsepackage_redaction_summary` |
| Otherwise | `redline_redaction_summary` |

Template selection logic lives in [redactionsummaryservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/redactionsummaryservice.py#L24).

## Summary Data Construction

The summary builder has two major branches.

### Standard branch

Most categories use `__packaggesummary(...)` in [redactionsummary.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/dts/redactionsummary.py#L26).

This branch:

1. Resolves the effective redaction layer.
2. Reads `sorteddocuments` to establish stitched document order.
3. Fetches stitched page counts and, for phased response packages, original page counts.
4. Loads page flags and deleted-page information from the database.
5. Filters the working page set based on category and phase.
6. Maps flagged pages to stitched page numbers and redaction sections.
7. Produces grouped summary entries such as consult, duplicate, not responsive, and phase-related sections depending on the category.

For non-MCF response-package and openinfo requests, the service consolidates all grouped section entries into one flat, range-sorted list before rendering.

### MCF personal response-package branch

`mcf` personal response-package and openinfo requests use `__packagesummaryforcfdrequests(...)` in [redactionsummary.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/dts/redactionsummary.py#L128).

This branch:

1. Reads record groupings from `summarydocuments.pkgdocuments[0].records`.
2. Maps page flags to stitched pages.
3. Applies phase filtering when needed.
4. Computes page ranges per record.
5. Associates redaction sections with each record.
6. Produces a record-oriented summary model instead of the standard grouped-flag model.

## Page-Flag Rules

Page-flag selection is category-sensitive.

| Category | Page flags loaded |
| --- | --- |
| `responsepackage`, `openinfo` | `Consult`, `Not Responsive`, `Duplicate`, `Phase` |
| All other summary-generating categories | `Consult`, `Phase` |

This is implemented in [redactionsummaryservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/redactionsummaryservice.py#L108).

Additional rules:

- `oipcreviewredline` removes duplicate and not-responsive sections from the final summary.
- `redline_phase{n}` and `responsepackage_phase{n}` restrict the summary to pages associated with the selected phase.
- Deleted pages are excluded from page calculations.

## One Summary per Package Group

The service iterates `summarydocuments.pkgdocuments` and generates one summary PDF per entry that contains `documentids`.

In practice:

- Redline usually generates one summary per division.
- Response package usually generates one summary for the package.
- MCF personal response package usually generates one summary for the package, but with record-level grouping inside the rendered summary.

## File Naming and Upload Location

The summary service derives the upload target from the first stitched file in the matching `attributes` entry.

Summary names are category-aware:

| Category pattern | Output naming rule |
| --- | --- |
| `responsepackage_phase{n}` | `{requestnumber} - Phase {n} - summary.pdf` |
| `responsepackage` | `{requestnumber} - summary.pdf` |
| `redline_phase{n}` | `{requestnumber} - Redline - Phase {n} - summary.pdf` |
| `oipcreviewredline` | `{requestnumber} - Redline - summary.pdf` |
| `openinfo` | `Redaction_Summary_{requestnumber}.pdf` |
| Other redline-like categories | `{requestnumber} - {category} - {divisionname?} - summary.pdf` |

The naming logic is in [redactionsummaryservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/redactionsummaryservice.py#L92).

## Rendering

After the summary data model is assembled:

1. `documentgenerationservice.generate_pdf(...)` resolves the configured template.
2. The service checks whether the CDOGS template hash is already cached.
3. If needed, it uploads the template to CDOGS and stores the returned hash code.
4. CDOGS renders the final PDF.

Rendering logic lives in [documentgenerationservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/documentgenerationservice.py#L30).

## Job Status Tracking

The document service records summary-specific job activity in `PDFStitchJob` using `category + "-summary"`.

Observed states:

- `redactionsummarystarted`
- `redactionsummaryuploaded`
- `error` with message `summary generation failed`

Reference: [pdfstitchjobactivity.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/dal/pdfstitchjobactivity.py#L15)

## Handoff to Zipping

Once summary generation completes:

1. Generated summary files are appended to the original `filestozip`.
2. The message is normalized back to JSON strings.
3. The combined package request is sent to the zipper stream.

Reference: [zippingservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/zippingservice.py#L6)

This means the final ZIP contains:

- The already-uploaded stitched package PDF files.
- The generated summary PDF files, if the category produces summaries.

## Failure Behavior

- Summary generation failures are caught inside `redactionsummaryservice.processmessage(...)`.
- The service records an error job activity row.
- It returns whatever summary files were successfully created before the failure, if any.
- The message is still forwarded to the zipper service, which means packaging can continue even if no summary PDF was generated.

## Practical Constraints

- Summary generation assumes the stitched package PDFs already exist in object storage.
- The quality of the summary depends directly on `summarydocuments.sorteddocuments`, `pkgdocuments`, page flags, deleted pages, and section metadata being consistent.
- `documentsetid` can alter the effective document set by expanding the document list from record groups before summary rendering.
