# Frontend Process for Building `triggerdownloadredline` Payload

## Purpose

This document describes how the frontend builds the request payload sent to `POST /api/triggerdownloadredline`.

It covers all frontend variants that use the same endpoint:

- standard redline
- consult package
- OIPC redline
- OIPC review redline
- phase-based redline

The implementation is centered in [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js).

## High-Level Flow

1. The user opens the package modal from the document-review UI.
2. The modal captures package options such as comments, duplicate pages, NR pages, consult options, and phase.
3. The frontend determines which documents belong in each package group.
4. The frontend calls the backend presigned-URL endpoint to get upload targets and package metadata.
5. The frontend builds the base `redlineZipperMessage`.
6. The frontend stitches and post-processes PDFs in the browser.
7. The frontend uploads the final stitched PDFs to object storage.
8. The frontend converts the uploaded files plus incompatible files into `attributes[*].files`.
9. Once all groups are ready, the frontend POSTs the final payload to `/api/triggerdownloadredline`.

## Main Entry Points

### Payload creation hook

- [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js)

### Modal inputs

- [ConfirmationModal.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/ConfirmationModal.js)

### API call

- [docReviewerService.tsx](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/apiManager/services/docReviewerService.tsx#L413)

### Presigned URL request

- [foiOSSService.tsx](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/apiManager/services/foiOSSService.tsx#L42)

## User Inputs That Affect the Payload

The modal drives several payload fields.

### Standard redline options

When `modalFor === "redline"`, the user can control:

- `includeComments`
- `includeNRPages`
- `includeDuplicatePages`
- `redlinePhase` when phases are enabled

Reference: [ConfirmationModal.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/ConfirmationModal.js#L82)

### Consult package options

When `modalFor === "consult"`, the user can control:

- which public bodies or custom consult bodies are included
- `includeNRPages`
- `includeDuplicatePages`
- `consultApplyRedlines`
- `consultApplyRedactions`

These inputs affect both which files are generated and what metadata is carried in the payload.

### OIPC behavior

OIPC behavior is determined by:

- the selected current layer
- the requested `layertype`

The modal suppresses phase selection when `validoipcreviewlayer` is true.

## Core State Used to Build the Payload

The hook stores package state in several React state variables:

| State | Purpose |
| --- | --- |
| `redlineCategory` | Frontend mode such as `redline`, `consult`, or `oipcreview`. |
| `redlinePhase` | Selected phase for phased redline output. |
| `includeComments` | Controls whether comments are included in the exported PDF and payload metadata. |
| `includeNRPages` | Controls NR page inclusion and payload metadata. |
| `includeDuplicatePages` | Controls duplicate-page inclusion and payload metadata. |
| `consultApplyRedlines` | Consult-specific toggle for preserving transparent redlines. |
| `consultApplyRedactions` | Consult-specific toggle for applying NR redactions. |
| `selectedPublicBodyIDs` | Consult-specific grouping keys. |
| `redlineZipperMessage` | The in-progress payload object eventually posted to the API. |
| `redlineStitchInfo` | Per-group upload targets and document IDs. |
| `redlineIncompatabileMappings` | Incompatible files that must be included without stitching. |

## Step 1: Determine Package Category

The frontend decides the API `category` by calling `getzipredlinecategory(layertype)`.

Reference: [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js#L1031)

Rules:

| Condition | Payload `category` |
| --- | --- |
| `redlineCategory === "consult"` | `consultpackage` |
| current layer is `oipc` and `layertype === "oipcreview"` | `oipcreviewredline` |
| current layer is `oipc` and not OIPC review | `oipcredline` |
| `redlineCategory === "redline"` and `redlinePhase` is set | `redline_phase{phase}` |
| otherwise | `redline` |

This is the main frontend switch that determines which downstream backend path will run.

## Step 2: Determine Package Groups

The frontend groups documents differently depending on variant.

### Standard redline and OIPC variants

For `redline` and `oipcreview`, documents are grouped by division.

The helper `getDivisionDocumentMappingForRedline(...)` creates entries like:

```json
{
  "divisionid": 87,
  "divisionname": "Minister of State",
  "documentlist": [...],
  "incompatableList": [...]
}
```

### Consult package

For consult packages, the frontend reuses the same division-oriented packaging flow, but substitutes selected public bodies as the grouping key.

Each selected public body or custom consult body becomes a package group.

This is why consult packaging still produces `divisionid` and `divisionname`-style payload entries later, even though the logical grouping is by consultees/public bodies.

## Step 3: Request Presigned URLs and Package Metadata

Before it can build final file entries, the frontend calls:

- [getFOIS3DocumentRedlinePreSignedUrl](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/apiManager/services/foiOSSService.tsx#L42)

That request includes:

- `ministryrequestID`
- `requestType`
- grouped `divdocumentList`
- `layertype`
- current layer name
- `redlinePhase`

The backend response supplies:

- `requestnumber`
- `bcgovcode`
- `issingleredlinepackage`
- top-level `s3path_save` for single-package mode
- per-group `s3path_save`
- per-document `s3path_load`
- normalized `divdocumentList`

Reference: [foiflowmasterdata.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/resources/foiflowmasterdata.py#L310)

This backend call is what gives the frontend enough information to finish the payload.

## Step 4: Build the Base Payload Object

After the presigned-URL response returns, the frontend initializes `redlineZipperMessage`:

Reference: [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js#L1442)

Base shape:

```json
{
  "ministryrequestid": "<foiministryrequestid>",
  "category": "<derived-category>",
  "attributes": [],
  "requestnumber": "<from-presigned-response>",
  "bcgovcode": "<from-presigned-response>",
  "summarydocuments": { "...": "..." },
  "redactionlayerid": "<current layer id>",
  "requesttype": "<request type>"
}
```

### Field sources

| Payload field | Source |
| --- | --- |
| `ministryrequestid` | `useParams().foiministryrequestid` |
| `category` | `getzipredlinecategory(layertype)` |
| `attributes` | built later after PDF upload/incompatible-file merge |
| `requestnumber` | presigned-URL response |
| `bcgovcode` | presigned-URL response |
| `summarydocuments` | `prepareredlinesummarylist(stitchDocuments)` |
| `redactionlayerid` | current Redux layer |
| `requesttype` | request info from Redux |

## Step 5: Build `summarydocuments`

The frontend creates `summarydocuments` by calling `prepareredlinesummarylist(stitchDocuments)`.

Reference: [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js#L1044)

The structure contains:

- `sorteddocuments`: a globally ordered document list
- `pkgdocuments`: package groups keyed by division or consult grouping

Typical shape:

```json
{
  "sorteddocuments": [26586, 26587, 26590],
  "pkgdocuments": [
    { "divisionid": "87", "documentids": [26586, 26587] },
    { "divisionid": "92", "documentids": [26590] }
  ]
}
```

Notes:

- In single-package mode, the frontend uses `"0"` as the synthetic package key.
- For consult packages, the logical grouping is by selected public body, but the generated structure still uses `divisionid`-style keys.

## Step 6: Stitch and Post-Process PDFs

Once the base payload exists, the frontend generates the actual PDF files that will later be referenced by `attributes[*].files`.

There are two broad stitching modes:

### Single-package mode

If `issingleredlinepackage === "Y"`, the frontend stitches all relevant documents into one package output.

Reference: [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js#L1087)

### Per-group mode

If `issingleredlinepackage === "N"`, the frontend creates one stitched PDF per division or consult group.

Reference: [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js#L1067)

## Step 7: Variant-Specific PDF Processing

The uploaded PDFs differ by variant before they are turned into payload file entries.

### Standard redline

Standard redline flow:

- stamps page numbers
- removes pages excluded by page mappings
- adds duplicate or NR watermarks when needed
- exports annotations
- optionally re-imports comments if `includeComments` is enabled

### Phase-based redline

Phase-based redline is still a redline payload, but:

- the category becomes `redline_phase{n}`
- page selection logic restricts the package to pages belonging to the chosen phase
- the per-attribute `phase` field is populated

### OIPC review redline

For `redlineCategory === "oipcreview"`:

- the category becomes `oipcreviewredline`
- the frontend identifies `s. 14` redactions
- those redactions are applied before upload
- the uploaded PDF becomes the source file referenced in the payload

Reference: [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js#L2059)

### OIPC redline

For the OIPC layer without OIPC review mode:

- the category becomes `oipcredline`
- the flow still uses the same payload-construction path
- OIPC-specific category selection happens earlier through `getzipredlinecategory(...)`

### Consult package

For `redlineCategory === "consult"`:

- if `consultApplyRedlines` is false, transparent redline annotations are removed from the exported package
- if `consultApplyRedactions` is true, NR redactions are applied
- pages outside the current consult group are removed
- consult-specific page filtering is applied before upload

Reference: [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js#L2160)

## Step 8: Upload Stitched PDFs to Object Storage

After post-processing, the frontend uploads each final PDF to the `s3path_save` returned by the presigned endpoint.

Reference:

- [saveFilesinS3](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/apiManager/services/foiOSSService.tsx#L78)
- [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js#L2108)

Only after this upload succeeds can the frontend add the file to the final API payload.

## Step 9: Convert Uploaded Files Into `attributes[]`

The final payload is assembled incrementally in `prepareMessageForRedlineZipping(...)`.

Reference: [useSaveRedlineForSignOff.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveRedlineForSignOff.js#L1536)

For each package group, the frontend builds:

```json
{
  "divisionid": 87,
  "divisionname": "Minister of State",
  "files": [
    {
      "filename": "Minister of State/ECC-4535-455 - redline - Minister of State.pdf",
      "s3uripath": "https://..."
    }
  ],
  "includeduplicatepages": true,
  "includenrpages": true,
  "phase": null,
  "includecomments": true,
  "documentsetid": 158
}
```

### Per-attribute field sources

| Field | Source |
| --- | --- |
| `divisionid` | current group metadata, only set in multi-package mode |
| `divisionname` | current group metadata, only set in multi-package mode |
| `files` | stitched upload path plus incompatible files |
| `includeduplicatepages` | current checkbox state |
| `includenrpages` | current checkbox state |
| `phase` | `redlinePhase` only when `redlineCategory === "redline"` |
| `includecomments` | current checkbox state |
| `documentsetid` | URL query parameter `documentsetid` |

### How `files[]` is built

The `files` array is a merge of:

1. the stitched PDF just uploaded to S3
2. any incompatible files that could not participate in stitching

If the package is multi-group:

- the stitched filename is prefixed with `divisionname/`

If the package is single-group:

- the filename is just the uploaded PDF filename

This explains why redline ZIPs preserve division folders in multi-package mode.

## Step 10: Final Dispatch to the API

Each successful group upload appends one `attributes[]` entry to `redlineZipperMessage`.

When the number of completed attribute entries matches the expected group count, the frontend calls:

- [triggerDownloadRedlines](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/apiManager/services/docReviewerService.tsx#L413)

That function POSTs the final payload to:

- `/api/triggerdownloadredline`

## Final Payload Shape

The final frontend payload sent to the API looks like:

```json
{
  "ministryrequestid": "21965",
  "category": "redline",
  "attributes": [
    {
      "divisionid": 87,
      "divisionname": "Minister of State",
      "files": [
        {
          "filename": "Minister of State/ECC-4535-455 - redline - Minister of State.pdf",
          "s3uripath": "https://..."
        }
      ],
      "includeduplicatepages": true,
      "includenrpages": true,
      "phase": null,
      "includecomments": true,
      "documentsetid": 158
    }
  ],
  "requestnumber": "ECC-4535-455",
  "bcgovcode": "ecc",
  "summarydocuments": {
    "sorteddocuments": [26586],
    "pkgdocuments": [
      {
        "divisionid": "87",
        "documentids": [26586]
      }
    ]
  },
  "redactionlayerid": 1,
  "requesttype": "general"
}
```

## Variant Summary

### Standard redline

- `category = "redline"`
- `phase = null`
- comments, duplicate pages, and NR pages come from modal checkboxes

### Phase-based redline

- `category = "redline_phase{n}"`
- `attributes[*].phase = n`
- phase also influences which pages are stitched and uploaded

### Consult package

- `category = "consultpackage"`
- groups are selected public bodies rather than divisions
- consult toggles affect the actual uploaded PDF content
- `phase` remains `null`

### OIPC redline

- `category = "oipcredline"`
- payload creation path is otherwise the same as standard redline

### OIPC review redline

- `category = "oipcreviewredline"`
- `s. 14` redactions are applied before upload

## Important Implementation Details

- The frontend does not send source document paths directly from the original document list. It sends the uploaded stitched PDF paths returned by the presigned flow plus incompatible-file paths.
- The payload is built only after object-storage upload succeeds.
- `documentsetid` is pulled from the URL query string, not from Redux state.
- `summarydocuments` is derived from the stitched document grouping, not from the uploaded `files[]` list.
- The payload object is mutated incrementally through `zipServiceMessage.attributes.push(...)`, then dispatched once all package groups are complete.
