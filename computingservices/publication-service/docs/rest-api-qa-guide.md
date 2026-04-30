# REST API QA Guide

This guide explains how to test the Publication Service REST API end to end in a dev environment. It is written for QA testers and developers who need to understand the request flow, expected side effects, and verification points.

Scope for this document:

- Covers only the REST API path.
- Assumes the dev environment already has the app deployed with Redis, Postgres, and S3-compatible object storage available.
- Does not cover Redis event ingestion, Redis completion events, or the async worker flow. See `docs/events.md` for event payloads.

## 1. What the REST API Does

The REST API exposes a synchronous publication path:

```text
QA/client
  -> POST /publications
  -> validate request
  -> copy source S3 objects to destination S3 prefix
  -> generate and upload an HTML index page
  -> update the matching sitemap XML
  -> return a completed JSON response
```

It also exposes a synchronous unpublish path:

```text
QA/client
  -> POST /publications/unpublish
  -> validate request
  -> delete public objects under the supplied public repository prefix
  -> remove the public URL from the matching sitemap XML
  -> return a completed JSON response
```

Important REST behavior:

- `POST /publications` and `POST /publications/unpublish` do not publish Redis events.
- Successful REST calls should not be verified by waiting for `*.publish.completed`, `*.sitemapping.completed`, or `*.unpublish.completed` Redis messages.
- Verify REST calls through the HTTP response, S3 object state, sitemap XML, and Postgres `workflow_request` rows.

## 2. Endpoints

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Confirms the service process is alive. |
| `/version` | `GET` | Shows build metadata for the deployed service. |
| `/publications` | `POST` | Publishes OpenInfo or Proactive Disclosure content. |
| `/publications/unpublish` | `POST` | Removes OpenInfo or Proactive Disclosure content. |

Both REST write endpoints require a JSON wrapper:

```json
{
  "publication_type": "openinfo",
  "payload": {}
}
```

Allowed `publication_type` values:

- `openinfo`
- `proactivedisclosure`

## 3. Dev Setup Checklist

Before testing, confirm these environment conditions with the deployment owner or platform notes:

- Publication Service is deployed and reachable at the dev base URL.
- Postgres migrations have run successfully.
- Redis is running, even though this REST test does not depend on Redis messages for success verification.
- The S3-compatible storage endpoint is reachable from the service.
- Source and destination buckets exist.
- Sitemap buckets and prefixes are configured for both OpenInfo and Proactive Disclosure.
- The configured `S3_PUBLIC_URL` points to a URL that QA can open in a browser.

Public bucket note:

Some dev object-storage deployments do not expose uploaded objects publicly by default. If the REST response returns a `public_url` but the browser gets `403`, `AccessDenied`, or a storage login prompt, the destination bucket may need to be made public. In this environment that may require adding the expected public-access marker/config file in the bucket, or applying the equivalent bucket policy used by the dev platform. Do this for both published-content buckets and sitemap buckets when required.

## 4. Test Data Setup

Use unique IDs and prefixes per test run so repeated QA runs do not collide.

Recommended test values:

```bash
export BASE_URL="https://publication-service-dev.example.gov.bc.ca"
export TENANT_ID="a7d9b2f1-4c3e-4e8b-9a21-1c2e8f7b9d10"
export RUN_ID="$(date -u +%Y%m%d%H%M%S)"
export OI_ID="HTH-2026-${RUN_ID}"
export PD_ID="PD-2026-${RUN_ID}"
```

Seed at least one source object before calling `POST /publications`.

OpenInfo example source and destination:

```text
source.bucket:      foi-raw
source.prefix:      qa/openinfo/{RUN_ID}/source/
destination.bucket: foi-published
destination.prefix: qa/openinfo/{RUN_ID}/public/
```

Proactive Disclosure example source and destination:

```text
source.bucket:      pd-raw
source.prefix:      qa/pd/{RUN_ID}/source/
destination.bucket: pd-published
destination.prefix: qa/pd/{RUN_ID}/public/
```

If testing locally with the repository Docker Compose stack, a source object can be seeded like this:

```bash
export AWS_ACCESS_KEY_ID=access_key
export AWS_SECRET_ACCESS_KEY=secret_key
export AWS_DEFAULT_REGION=us-east-1

aws --endpoint-url http://localhost:8333 s3 mb s3://foi-raw
aws --endpoint-url http://localhost:8333 s3 mb s3://foi-published
printf "qa openinfo test file\n" | aws --endpoint-url http://localhost:8333 \
  s3 cp - "s3://foi-raw/qa/openinfo/${RUN_ID}/source/test-document.txt"
```

For deployed dev, use the approved bucket access method for that environment.

## 5. Smoke Test the Deployment

Run:

```bash
curl -i "${BASE_URL}/health"
curl -i "${BASE_URL}/version"
```

Expected:

- `/health` returns HTTP `200`.
- `/version` returns HTTP `200` with build metadata.

## 6. Publish OpenInfo

Request:

```bash
curl -sS -X POST "${BASE_URL}/publications" \
  -H "Content-Type: application/json" \
  -d "{
    \"publication_type\": \"openinfo\",
    \"payload\": {
      \"tenant_id\": \"${TENANT_ID}\",
      \"axis_request_id\": \"${OI_ID}\",
      \"description\": \"QA OpenInfo REST publication test\",
      \"published_date\": \"2026-04-27\",
      \"contributor\": \"Ministry of Health\",
      \"fees\": 0,
      \"applicant_type\": \"Individual\",
      \"source\": {
        \"bucket\": \"foi-raw\",
        \"prefix\": \"qa/openinfo/${RUN_ID}/source/\"
      },
      \"destination\": {
        \"bucket\": \"foi-published\",
        \"prefix\": \"qa/openinfo/${RUN_ID}/public/\"
      }
    }
  }"
```

Expected HTTP result:

- Status is HTTP `200`.
- JSON response has `status: "completed"`.
- `publication_type` is `openinfo`.
- `publication_id` matches `axis_request_id`.
- `public_url` points to the generated HTML page.
- `html_key` ends with `${OI_ID}.html`.
- `sitemap_result` is usually `written` for a new sitemap entry.

Example response shape:

```json
{
  "status": "completed",
  "publication_type": "openinfo",
  "publication_id": "HTH-2026-20260427120000",
  "public_url": "https://dev-public-storage.example/foi-published/qa/openinfo/20260427120000/public/HTH-2026-20260427120000.html",
  "html_key": "qa/openinfo/20260427120000/public/HTH-2026-20260427120000.html",
  "sitemap_index_key": "openinfopub/sitemap/sitemap_index.xml",
  "sitemap_page_key": "openinfopub/sitemap/sitemap_pages_1.xml",
  "sitemap_result": "written"
}
```

## 7. Verify OpenInfo Publish

Verify S3 destination objects:

- The original source objects were copied under the destination prefix.
- The generated HTML file exists at the response `html_key`.
- The HTML file is readable through the response `public_url` if the bucket is configured for public reads.

Verify sitemap:

- The `sitemap_index_key` exists in the configured OpenInfo sitemap bucket.
- The `sitemap_page_key` exists when returned.
- The sitemap page contains the response `public_url`.

Verify Postgres:

```sql
SELECT event_type, kind, state, payload, result, completed_at
FROM workflow_request
WHERE payload->>'axis_request_id' = '<OI_ID>'
   OR payload->>'publication_id' = '<OI_ID>'
ORDER BY first_seen_at DESC;
```

Expected rows:

- A completed OpenInfo publication row with `kind = 'openinfo'`.
- A completed OpenInfo sitemap row with `kind = 'openinfo_sitemap'`.

## 8. Publish Proactive Disclosure

Request:

```bash
curl -sS -X POST "${BASE_URL}/publications" \
  -H "Content-Type: application/json" \
  -d "{
    \"publication_type\": \"proactivedisclosure\",
    \"payload\": {
      \"tenant_id\": \"${TENANT_ID}\",
      \"axis_request_id\": \"${PD_ID}\",
      \"description\": \"QA Proactive Disclosure REST publication test\",
      \"published_date\": \"2026-04-27\",
      \"contributor\": \"Ministry of Transportation\",
      \"fees\": 0,
      \"applicant_type\": null,
      \"proactivedisclosure_category\": \"Travel Expenses\",
      \"report_period\": \"2026-Q1\",
      \"foiministryrequest_id\": 22318,
      \"foirequest_id\": 22318,
      \"source\": {
        \"bucket\": \"pd-raw\",
        \"prefix\": \"qa/pd/${RUN_ID}/source/\"
      },
      \"destination\": {
        \"bucket\": \"pd-published\",
        \"prefix\": \"qa/pd/${RUN_ID}/public/\"
      },
      \"sitemap_pages\": \"\",
      \"additionalfiles\": [
        {
          \"additionalfileid\": 67,
          \"filename\": \"qa-file.pdf\",
          \"s3uripath\": \"https://example.gov.bc.ca/qa-file.pdf\",
          \"isactive\": true
        }
      ],
      \"openinfo_id\": 0
    }
  }"
```

Expected HTTP result:

- Status is HTTP `200`.
- JSON response has `status: "completed"`.
- `publication_type` is `proactivedisclosure`.
- `publication_id` matches `axis_request_id`.
- `public_url`, `html_key`, and sitemap fields are populated.

## 9. Verify Proactive Disclosure Publish

Verify S3 destination objects:

- The original source objects were copied under the PD destination prefix.
- The generated HTML file exists at the response `html_key`.
- The response `public_url` opens in a browser when public bucket access is configured.

Verify sitemap:

- The `sitemap_index_key` exists in the configured Proactive Disclosure sitemap bucket.
- The `sitemap_page_key` exists when returned.
- The sitemap page contains the response `public_url`.

Verify Postgres:

```sql
SELECT event_type, kind, state, payload, result, completed_at
FROM workflow_request
WHERE payload->>'axis_request_id' = '<PD_ID>'
   OR payload->>'publication_id' = '<PD_ID>'
ORDER BY first_seen_at DESC;
```

Expected rows:

- A completed Proactive Disclosure publication row with `kind = 'pd'`.
- A completed Proactive Disclosure sitemap row with `kind = 'pd_sitemap'`.

## 10. Unpublish OpenInfo

Use values returned by the OpenInfo publish response.

Request:

```bash
curl -sS -X POST "${BASE_URL}/publications/unpublish" \
  -H "Content-Type: application/json" \
  -d "{
    \"publication_type\": \"openinfo\",
    \"payload\": {
      \"tenant_id\": \"${TENANT_ID}\",
      \"publication_id\": \"${OI_ID}\",
      \"public_url\": \"<public_url from publish response>\",
      \"public_repository\": {
        \"bucket\": \"foi-published\",
        \"prefix\": \"qa/openinfo/${RUN_ID}/public/\"
      },
      \"last_modified\": \"2026-04-27\"
    }
  }"
```

Expected HTTP result:

- Status is HTTP `200`.
- JSON response has `status: "completed"`.
- `publication_type` is `openinfo`.
- `objects_deleted` is the number of deleted objects under the public repository prefix.
- `sitemap_result` should indicate the sitemap entry was removed or already absent.

Verify:

- Destination prefix no longer contains the copied public objects.
- The public URL no longer opens successfully.
- The OpenInfo sitemap page no longer contains that public URL.
- Postgres has a completed row with `kind = 'openinfo_unpublish'`.

## 11. Unpublish Proactive Disclosure

Use values returned by the Proactive Disclosure publish response.

Request:

```bash
curl -sS -X POST "${BASE_URL}/publications/unpublish" \
  -H "Content-Type: application/json" \
  -d "{
    \"publication_type\": \"proactivedisclosure\",
    \"payload\": {
      \"tenant_id\": \"${TENANT_ID}\",
      \"publication_id\": \"${PD_ID}\",
      \"public_url\": \"<public_url from publish response>\",
      \"public_repository\": {
        \"bucket\": \"pd-published\",
        \"prefix\": \"qa/pd/${RUN_ID}/public/\"
      },
      \"last_modified\": \"2026-04-27\"
    }
  }"
```

Expected HTTP result:

- Status is HTTP `200`.
- JSON response has `status: "completed"`.
- `publication_type` is `proactivedisclosure`.
- `objects_deleted` is the number of deleted objects under the public repository prefix.
- `sitemap_result` should indicate the sitemap entry was removed or already absent.

Verify:

- Destination prefix no longer contains the copied public objects.
- The public URL no longer opens successfully.
- The Proactive Disclosure sitemap page no longer contains that public URL.
- Postgres has a completed row with `kind = 'pd_unpublish'`.

## 12. Negative Test Cases

Malformed JSON:

```bash
curl -i -X POST "${BASE_URL}/publications" \
  -H "Content-Type: application/json" \
  -d "{"
```

Expected: HTTP `400`.

Unsupported publication type:

```bash
curl -i -X POST "${BASE_URL}/publications" \
  -H "Content-Type: application/json" \
  -d '{"publication_type":"bad","payload":{}}'
```

Expected: HTTP `400`.

Missing payload:

```bash
curl -i -X POST "${BASE_URL}/publications" \
  -H "Content-Type: application/json" \
  -d '{"publication_type":"openinfo"}'
```

Expected: HTTP `400`.

Wrong method:

```bash
curl -i -X GET "${BASE_URL}/publications"
```

Expected: HTTP `405`.

Overlapping source and destination prefixes:

```json
{
  "source": {"bucket": "foi-published", "prefix": "qa/openinfo/1/"},
  "destination": {"bucket": "foi-published", "prefix": "qa/openinfo/1/public/"}
}
```

Expected: HTTP `400`, because the service rejects same-bucket overlapping prefixes.

Missing source objects:

- If the source prefix is empty, the copy step is a successful no-op.
- The service still generates the HTML index and updates the sitemap.
- Use this only as a behavior check; normal QA publication tests should include at least one source object.

## 13. Common Troubleshooting

`public_url` returns `403` or `AccessDenied`:

- Confirm the object exists at the destination key.
- Confirm `S3_PUBLIC_URL` points to the correct public host.
- Confirm the destination bucket is public in dev.
- If this dev storage requires a public marker/config file in the bucket, add it to the destination and sitemap buckets.

HTTP `400` with schema violation:

- Confirm all required fields are present.
- OpenInfo publish requires `tenant_id`, `source`, `destination`, and `axis_request_id`.
- Proactive Disclosure publish also requires `proactivedisclosure_category` and `report_period`.
- Publish bucket names must use S3-compatible lowercase bucket naming.
- `last_modified` for unpublish must use `YYYY-MM-DD`.

HTTP `500`:

- Check service logs for S3, Postgres, or sitemap update errors.
- Confirm Postgres is reachable and migrations are applied.
- Confirm source and destination buckets exist.
- Confirm the service has S3 read/write permissions for source, destination, and sitemap buckets.

Redis streams do not show completion messages:

- This is expected for REST API testing.
- REST calls complete synchronously and do not emit Redis completion events.

## 14. QA Pass Criteria

A REST API test pass means:

- Health and version endpoints are reachable.
- OpenInfo publish returns HTTP `200` and `status = completed`.
- OpenInfo destination objects and HTML page exist.
- OpenInfo sitemap contains the published URL after publish.
- OpenInfo unpublish returns HTTP `200` and removes the public objects and sitemap URL.
- Proactive Disclosure publish returns HTTP `200` and `status = completed`.
- Proactive Disclosure destination objects and HTML page exist.
- Proactive Disclosure sitemap contains the published URL after publish.
- Proactive Disclosure unpublish returns HTTP `200` and removes the public objects and sitemap URL.
- Expected negative cases return HTTP `400` or `405` without creating incorrect public artifacts.
