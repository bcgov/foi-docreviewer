# FOI DOC REVIEWER API

## `POST /api/triggerdownloadredline`

Triggers creation of a redline download package after the frontend has already generated and uploaded the per-division or single-package redline PDFs to object storage.

This endpoint does not return the ZIP file. It records a PDF stitch job and publishes a message to the downstream document service stream, where summary generation and zipping are completed asynchronously.

### Authentication

- Requires bearer token authentication.
- The route is protected by `@auth.require` in the API layer.

### What the endpoint does

When a valid request is received, the API:

1. Validates the payload with `RedlineSchema`.
2. Creates a `PDFStitchJob` row with status `pushedtostream`.
3. Flattens `attributes[*].files[*]` into a `filestozip` list.
4. Publishes a message to the document service Redis stream.
5. Returns a synchronous acknowledgement to the caller.

### Request contract

#### Top-level fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `ministryrequestid` | `string` | Yes | FOI request identifier. Stored as integer in job status creation. |
| `category` | `string` | Yes | Usually `redline`. Phase-based variants are also supported by downstream logic. |
| `requestnumber` | `string` | Yes | Human-readable FOI request number, for example `ECC-4535-455`. |
| `bcgovcode` | `string` | Yes | Ministry code, for example `ecc`. |
| `attributes` | `array` | Yes | One entry per division/package payload being zipped. |
| `summarydocuments` | `object` | No | Document ordering/grouping metadata used by downstream summary generation. |
| `redactionlayerid` | `integer` | Yes | Redaction layer identifier, for example `1` for Redline. |
| `requesttype` | `string` | Yes | Request classification, for example `general` or `personal`. |

#### `attributes[]` fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `divisionid` | `integer` | No | Present for multi-division redline packages. |
| `divisionname` | `string` | No | Used for division-specific packaging and naming. |
| `files` | `array` | Yes | Files that should be included in the output ZIP. |
| `includeduplicatepages` | `boolean` | No | Indicates duplicate-page content should be included in the package. |
| `includenrpages` | `boolean` | No | Indicates NR pages should be included. |
| `phase` | `integer` or `null` | No | Used for phase-based redline generation. |
| `includecomments` | `boolean` | No | Indicates comment content should be included in the generated package. |
| `documentsetid` | `integer` | No | Optional grouping identifier carried downstream. |

#### `attributes[].files[]` fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `filename` | `string` | Yes | ZIP entry name. Can include folder segments such as `Minister of State/...pdf`. |
| `s3uripath` | `string` | Yes | Source object storage path for the file to zip. |

#### `summarydocuments` fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `sorteddocuments` | `array<int>` | No | Ordered list of source document IDs. |
| `pkgdocuments` | `array<object>` | No | Groupings used by summary generation. |

#### `summarydocuments.pkgdocuments[]` fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `divisionid` | `integer` | No | Division associated with the document group. |
| `documentids` | `array<int>` | Yes | Documents represented in that package group. |

### Sample request

```bash
curl 'https://dev-reviewer-api.apps.silver.devops.gov.bc.ca/api/triggerdownloadredline' \
  -H 'Accept: application/json, text/plain, */*' \
  -H 'Authorization: Bearer <TOKEN>' \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "ministryrequestid": "21965",
    "category": "redline",
    "attributes": [
      {
        "divisionid": 87,
        "divisionname": "Minister of State",
        "files": [
          {
            "filename": "Minister of State/ECC-4535-455 - redline - Minister of State.pdf",
            "s3uripath": "https://citz-foi-prod.objectstore.gov.bc.ca/ecc-dev-e/ECC-4535-455/redline/Minister of State/ECC-4535-455 - redline - Minister of State.pdf"
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
          "divisionid": 87,
          "documentids": [26586]
        }
      ]
    },
    "redactionlayerid": 1,
    "requesttype": "general"
  }'
```

### Successful response

```json
{
  "status": true,
  "message": "Added to stream"
}
```

### Failure modes

| HTTP status | Scenario | Notes |
| --- | --- | --- |
| `400` | Malformed JSON or missing expected keys | Returned when a `KeyError` is raised in the resource. |
| `500` | Business/service failure | For example, downstream stream publish failure or other business exception. |

### Operational notes

- This endpoint is asynchronous by design. A `200` response only confirms that the request was accepted and the stream publish succeeded.
- The ZIP payload is assembled from the flattened set of all files in `attributes[*].files[*]`.
- `summarydocuments`, `includecomments`, `includeduplicatepages`, `includenrpages`, `phase`, and `documentsetid` are forwarded for downstream processing; this route itself does not interpret those values beyond schema validation and message packaging.
- The resource for this endpoint is implemented in `api/reviewer_api/resources/redaction.py`, and the service logic is in `api/reviewer_api/services/radactionservice.py`.
