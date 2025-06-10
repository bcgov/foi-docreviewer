# Response Package Creation Documentation

This document describes how the Response Package is created in the FOI Document Reviewer app, focusing on the main flow in `Redlining.js` and `useSaveResponsePackage.js`.

---

## Overview

The Response Package is a redacted PDF package generated for end users (applicants). **All steps in the creation process are performed on the frontend, in the user's browser, using the Apryse (PDFTron) WebViewer library.** The Apryse document object (doc) in the browser is used to apply redactions, remove pages, and generate the final PDF. This ensures that sensitive information is redacted.

### Key Files

- `Redlining.js` (UI logic, triggers package creation)
- `useSaveResponsePackage.js` (core logic for package creation)
- `useSaveRedlineForSignOff.js` (shared logic for redline/consult/OIPC packages)
- `CreateResponsePDF.js` (UI and modal logic for package creation)

---

## High-Level Steps

1. **User Initiates Response Package Creation**
   - User clicks the "Create Response Package" button in the UI (in `Redlining.js`).
   - This calls the `saveResponsePackage` function from `useSaveResponsePackage.js`, passing in the current document viewer, annotation manager, document list, page mappings, page flags, and other metadata.

2. **Prepare Data and Pre-Signed S3 URL**
   - The function gathers the current document list, page mappings, and page flags.
   - It requests a pre-signed S3 URL from the backend for uploading the final PDF. This is done via an API call (see `getResponsePackagePreSignedUrl`).
   - Metadata for the response package (such as request ID, document IDs, user info etc) is also prepared for backend processing.

3. **Apply Redactions**
   - The Apryse WebViewer's `annotationManager.applyRedactions()` is called. This permanently removes all content under redaction annotations from the PDF.
   - This step is critical for ensuring sensitive information is not present in the final package.
   - All redaction logic is handled in the browser.

4. **Remove Pages as Needed**
   - Pages flagged for removal (e.g., "Withheld in Full", "Duplicate", "Not Responsive") are identified using the page flags and page mappings.
   - The code uses Apryse's API to remove these pages from the document (`doc.removePages(pagesToRemove)`).
   - This ensures that pages not meant for disclosure are not included in the response package.

5. **Remove Bookmarks**
   - All bookmarks are removed from the PDF to prevent navigation to removed or redacted content.
   - This is done by iterating through the document's bookmarks and deleting them using the Apryse API.

6. **Stamp Page Numbers**
   - The function `stampPageNumberResponse` is called to add page numbers to each page using the Apryse PDFNet Stamper API.
   - This ensures the final package is paginated for reference.

7. **Export and Re-Apply Section Names/Widgets**
   - After redactions are applied, only FreeText and Widget annotations (used for section names and form fields) are exported.
   - These annotations are then re-imported into the document so that section names and form fields are preserved in the final PDF.
   - This is done using `annotationManager.exportAnnotations()` and `annotationManager.importAnnotations()`.

8. **Save Final PDF to S3**
   - The final PDF is generated as a Blob using Apryse's document export functionality.
   - The Blob is uploaded to S3 using the pre-signed URL via a direct HTTP PUT request (see `saveFilesinS3`).

9. **Trigger Zipping Service**
   - After the PDF is uploaded, a message is sent to the backend to trigger the zipping and packaging of the response package for download by the end user.
   - This is done by calling `triggerDownloadFinalPackage` with the relevant metadata.
   - The backend zipping service will create a downloadable zip file for the applicant.

10. **UI Feedback**
    - Toast notifications are shown to the user at each step (start, success, error).
    - The page is refreshed after completion to reflect the new package status.

---

## Detailed Code Flow

### In `Redlining.js`:
- The `saveResponsePackage` function is imported and called when the user clicks the button, passing all required parameters (document viewer, annotation manager, document list, page mappings, page flags, etc).
- Handles UI state and feedback for the user.

### In `useSaveResponsePackage.js`:
- The main function, `saveResponsePackage`, performs the following:
  1. Prepares S3 upload and metadata by calling `getResponsePackagePreSignedUrl`.
  2. Applies redactions using `annotationManager.applyRedactions()`.
  3. Identifies and removes pages flagged for removal using `doc.removePages(pagesToRemove)`.
  4. Removes all bookmarks from the document.
  5. Stamps page numbers using `stampPageNumberResponse` and the Apryse PDFNet Stamper API.
  6. Exports FreeText and Widget annotations, then re-imports them after redactions are applied.
  7. Converts the document to a Blob and uploads it to S3 using `saveFilesinS3` and the pre-signed URL.
  8. Notifies the backend to zip and prepare the package by calling `triggerDownloadFinalPackage`.
  9. Provides UI feedback and refreshes the page.

### In `useSaveRedlineForSignOff.js`:
- Contains shared logic for redline, consult, and OIPC packages, including page mapping, annotation export, and S3 upload helpers.
- Handles phased redactions and consult package logic.

### In `CreateResponsePDF.js`:
- Handles UI logic for modals and package creation buttons.
- Provides user warnings and confirmation dialogs before package creation.

---

## Configuration, Permissions, and Security

- **Frontend-Only Redaction:** All redactions and page removals are performed in the browser. No unredacted data is sent to the backend or S3.
- **S3 Upload:** The app uses pre-signed S3 URLs for secure, direct uploads from the browser. The backend never receives the unredacted PDF.
- **Authentication:** The app is secured with SSO (Keycloak). Only authorized users can create and upload response packages.
- **Dependencies:** Requires a valid Apryse (PDFTron) WebViewer license. See `package.json` for dependencies.

---

## Limitations and Known Issues

- **Browser Memory:** Large PDFs may cause browser memory issues during PDF loading, redaction and export.

---

## Summary Table

| Step                      | Description                                                                                 |
|---------------------------|---------------------------------------------------------------------------------------------|
| User Action               | User clicks "Create Response Package"                                                       |
| Prepare S3 Upload         | Get pre-signed S3 URL, prepare metadata                                                    |
| Apply Redactions          | Permanently redact sensitive content using Apryse API                                       |
| Remove Pages              | Remove flagged pages (e.g., Withheld in Full, Duplicate, Not Responsive)                    |
| Remove Bookmarks          | Remove all bookmarks from the PDF                                                           |
| Stamp Page Numbers        | Add page numbers to each page using Apryse Stamper API                                      |
| Export Section Names      | Export and re-apply FreeText/Widget annotations                                             |
| Save to S3                | Upload the final PDF to S3 using pre-signed URL                                            |
| Trigger Zipping           | Notify backend to zip and prepare the package                                               |
| UI Feedback               | Show progress and completion to user                                                        |

---

## Additional Notes

- Apryse (PDFTron) WebViewer ensures all redactions are securely and permanently applied before distribution.
- All logic for redaction, page removal, and PDF generation is handled in the browser
- For further details, see the code in `Redlining.js`, `useSaveResponsePackage.js`, and `useSaveRedlineForSignOff.js`.
