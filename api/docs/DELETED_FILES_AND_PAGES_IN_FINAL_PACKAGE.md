# Deleted Files and Pages in Final Package Workflow

## Purpose

This document explains how deleted content is handled when the application creates a final package for the applicant.

There are two different deletion concepts in this codebase, and they behave differently:

1. deleted files or records
2. deleted pages inside otherwise active files

The distinction matters:

- deleted files are excluded before final-package generation starts
- deleted pages remain part of an active document, but are removed from page mapping, final-package output, and summary calculations

This document covers both the frontend and backend workflow.

## Terminology

### Deleted file

A deleted file is represented in the backend by `DocumentDeleted`. It marks an entire document or record path as deleted for a request.

Reference: [DocumentDeleted.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/models/DocumentDeleted.py)

### Deleted page

A deleted page is represented in the backend by `DocumentDeletedPages`. It marks one or more page numbers as deleted for a specific active document.

Reference: [DocumentDeletedPages.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/models/DocumentDeletedPages.py)

## High-Level Behavior

### Deleted files

Deleted files are excluded upstream, before the final-package workflow builds its `documentList`.

Effect:

- the user does not package them
- they are not stitched into the final PDF
- they are not included in summary generation
- they are not part of the final ZIP

### Deleted pages

Deleted pages remain associated with an active document, but they are removed from:

- frontend page mapping
- stitched-page calculations
- final PDF assembly
- summary generation

Effect:

- the document can still appear in the final package
- the deleted pages inside that document are excluded

## End-to-End Flow

1. A user deletes a whole file or specific pages.
2. The backend persists either `DocumentDeleted` or `DocumentDeletedPages`.
3. A page-calculator job is triggered so downstream page metadata is refreshed.
4. The frontend loads the request documents and deleted-page metadata.
5. The final-package workflow builds page mappings using only non-deleted pages.
6. The frontend removes additional pages for package rules such as duplicate, NR, withheld-in-full, and phase filtering.
7. The final-package PDF is uploaded to object storage.
8. The API receives the final-package payload and triggers summary generation and zipping.
9. The backend summary generator excludes deleted pages again from summary calculations.
10. The zipper packages only the already-generated final PDF and summary PDF.

## Part 1: Whole Deleted Files

### How a file is marked deleted

The backend file-deletion path is implemented in [documentservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/services/documentservice.py#L429).

`deletedocument(...)`:

- inserts rows into `DocumentDeleted`
- stores the deleted path prefix
- triggers a page-calculator job on success

This means file deletion is a backend data decision, not just a frontend filter.

### How deleted files are resolved

The system uses `DocumentMaster.getdeleted(ministryrequestid)` to resolve which document masters are deleted for the request.

Reference: [DocumentMaster.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/models/DocumentMaster.py#L167)

That result is then used to compute active document IDs:

- [Documents.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/models/Documents.py#L167)

`getactivedocumentidsbyrequest(...)` excludes documents whose `documentmasterid` is in the deleted set.

### Frontend consequence

By the time the frontend builds the final package, deleted files are generally already missing from the request’s active `documentList`.

In practical terms:

- the deleted file does not appear in the package builder inputs
- the deleted file is never stitched into the applicant package
- the deleted file is absent from `summarydocuments.sorteddocuments`

### Backend consequence

Because deleted files are absent from the active document list:

- the presigned final-package endpoint is never asked to create a package output for them
- the final stitched PDF never contains them
- summary generation never counts them
- zipping never sees them

## Part 2: Deleted Pages

Deleted pages are handled separately from deleted files.

### How deleted pages are stored

The service [docdeletedpageservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/api/reviewer_api/services/docdeletedpageservice.py#L12) creates `DocumentDeletedPages` rows and updates page counts.

It also triggers a page-calculator job after successful persistence.

### How deleted pages are loaded

The frontend maintains deleted-page state in Redux as `deletedDocPages`.

The main document/home workflow fetches that state and passes it into the page-mapping builder in [Home.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/Home.js#L128).

## Frontend Workflow for Deleted Pages in Final Package

The final-package frontend logic lives in [useSaveResponsePackage.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveResponsePackage.js).

### Step 1: Build page mappings without deleted pages

The initial page-mapping logic uses `getDocumentPages(...)`:

- [utils.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/utils.js#L167)

That helper:

- reads deleted pages for the document from `deletedDocPages`
- builds the document page array from `1..originalPagecount`
- omits any deleted page numbers

This means deleted pages are removed before stitched page numbering is calculated.

### Step 2: Build stitched page lookup from filtered page arrays

`prepareMapperObj(...)` in [Home.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/Home.js#L209) uses those filtered page arrays to construct:

- `stitchedPageLookup`
- `docIdLookup`
- `redlineDocIdLookup`

Because deleted pages are already missing here:

- they receive no stitched page number
- later steps cannot accidentally map them into the final package

### Step 3: Remove additional pages for final-package rules

Inside `saveResponsePackage(...)`, the frontend builds `pagesToRemove` from package rules:

- duplicate pages
- not responsive pages
- phase exclusions
- pages without flags in phase mode

Reference: [useSaveResponsePackage.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveResponsePackage.js#L245)

Important point:

- deleted pages are not added here because they were already removed from the stitched page mapping earlier

### Step 4: Remove pages from the package PDF

After applying redactions, the frontend removes the calculated `pagesToRemove` from the in-browser PDF:

- [useSaveResponsePackage.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveResponsePackage.js#L320)

Because deleted pages never received stitched page positions, they are already absent from the package at this stage.

### Step 5: Remove withheld-in-full pages after page stamping

After page numbers are stamped, the frontend recalculates and removes `Withheld in Full` pages:

- [useSaveResponsePackage.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveResponsePackage.js#L343)

This is separate from deleted-page logic, but the end result is similar: those pages do not survive into the uploaded final PDF.

### Step 6: Upload only the filtered final package PDF

The frontend uploads the final applicant package PDF to object storage:

- [useSaveResponsePackage.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveResponsePackage.js#L408)

At this point:

- deleted files are already absent from the source document list
- deleted pages are already absent from the uploaded PDF

## Final-Package Payload Impact

The frontend final-package payload contains:

- one uploaded final package PDF in `attributes[0].files`
- `summarydocuments`
- category metadata

Reference: [useSaveResponsePackage.js](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/web/src/components/FOI/Home/CreateResponsePDF/useSaveResponsePackage.js#L214)

Deleted content affects this payload indirectly:

### Deleted files

- deleted files do not appear in `documentList`
- therefore they do not contribute to the stitched final PDF
- therefore they do not contribute to `summarydocuments`

### Deleted pages

- deleted pages do not receive stitched page numbers
- therefore they do not exist in the uploaded final package PDF
- the payload still references the same document ID, but only the remaining pages survive

## Backend Summary Generation Impact

Even though deleted pages are already filtered out on the frontend, the backend summary generator excludes them again when computing summary ranges and sections.

The summary path is implemented in:

- [redactionsummaryservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/redactionsummaryservice.py)
- [redactionsummary.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/dts/redactionsummary.py)

### How backend summary generation gets deleted pages

`documentpageflag().getdeletedpages(...)` reads deleted-page rows from `DocumentDeletedPages`.

Reference: [documentpageflag.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/dal/documentpageflag.py#L219)

### How deleted pages affect summary generation

The summary builder uses deleted pages to:

- exclude deleted pages from section calculations
- avoid counting deleted pages when computing stitched page ranges
- avoid including deleted pages in response-package summaries

Relevant code:

- [redactionsummary.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/dts/redactionsummary.py#L62)
- [redactionsummary.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/dts/redactionsummary.py#L470)
- [redactionsummary.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/DocumentServices/services/dts/redactionsummary.py#L569)

This is an important defense-in-depth behavior:

- the frontend excludes deleted pages from the PDF
- the backend excludes deleted pages from the summary data model

### Deleted files and backend summary generation

Deleted files are not typically present in `summarydocuments.sorteddocuments` because they were excluded earlier from the active document set.

As a result:

- the summary generator does not see them as package inputs
- they do not contribute ranges, counts, or sections

## Backend Zipping Impact

The zipper does not make deletion decisions itself.

The zipper only packages whatever files are listed in `filestozip`.

Reference: [zipperservice.py](/home/alvesfc/workspace/bcgov/sync/foi-docreviewer/computingservices/ZippingServices/services/zipperservice.py#L105)

That means:

### Deleted files

- never reach the zipper as independent source files for the final package
- are absent because they were excluded earlier from the active package build

### Deleted pages

- are absent because the uploaded final package PDF already excludes them
- the zipper simply packages the filtered final PDF and generated summary PDF

## Practical Examples

### Example 1: Whole file deleted

1. A record is marked deleted through `DocumentDeleted`.
2. The request’s active document set no longer includes that record.
3. The frontend final-package flow never sees it in `documentList`.
4. The final package PDF excludes it completely.
5. The summary excludes it completely.
6. The ZIP excludes it completely.

### Example 2: Two pages deleted from an active document

1. Pages `3` and `4` are stored in `DocumentDeletedPages`.
2. The frontend mapper builds page arrays without `3` and `4`.
3. The stitched final-package PDF is generated from the remaining pages only.
4. The backend summary generator also excludes pages `3` and `4`.
5. The ZIP contains the final package PDF without those pages.

## Decision Summary

### When content is excluded before final package creation

- whole deleted files
- deleted pages via frontend page mapping

### When content is excluded again downstream

- deleted pages during summary generation

### What the zipper does

- no independent deletion logic
- packages the already-filtered outputs

## Key Takeaway

The final-package workflow handles deleted files and deleted pages in different layers:

- deleted files are excluded at the data-selection stage
- deleted pages are excluded at page-mapping, PDF-generation, and summary-generation stages

By the time zipping happens, deletion decisions have already been made. The ZIP contains only the filtered final package and filtered summary outputs.
