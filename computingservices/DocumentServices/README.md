# DocumentServices

Python service that consumes document-processing messages from Redis, generates redaction summary PDFs, uploads the generated files to S3-compatible storage, and forwards the updated payload to the zipper stream.

## What This Service Does

- Reads messages from the `DOCUMENTSERVICE_STREAM_KEY` Redis stream.
- Creates or reuses redaction summary templates through CDOGS.
- Pulls supporting metadata from the Document Service and FOI PostgreSQL databases.
- Uploads generated summary PDFs to S3-compatible storage.
- Publishes the updated message to the zipper stream.

The runtime entrypoint is [`__main__.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/__main__.py), which starts the Typer-based stream reader in [`rstreamio/reader/documentservicestreamreader.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/rstreamio/reader/documentservicestreamreader.py).

## Project Structure

- [`__main__.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/__main__.py): application entrypoint
- [`rstreamio/reader/documentservicestreamreader.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/rstreamio/reader/documentservicestreamreader.py): Redis consumer loop
- [`services/redactionsummaryservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/services/redactionsummaryservice.py): summary generation orchestration
- [`services/documentgenerationservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/services/documentgenerationservice.py): CDOGS template and PDF generation
- [`services/s3documentservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/services/s3documentservice.py): S3 upload handling
- [`services/zippingservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/services/zippingservice.py): forwards payloads to zipper
- [`utils/foidocumentserviceconfig.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/utils/foidocumentserviceconfig.py): environment loading
- [`templates/`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/templates): DOCX templates used by CDOGS

## Prerequisites

- Python `3.10.x`
- `pip`
- Redis reachable from your machine
- PostgreSQL access for:
  - Document Service database
  - FOI database
- Access to:
  - CDOGS API and token endpoint
  - S3-compatible document storage
- Local build dependencies for `psycopg2`
  - Ubuntu/Debian: `sudo apt-get install libpq-dev gcc`

## Local Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If you need to leave the environment later:

```bash
deactivate
```

### 2. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

The service loads environment variables with `python-dotenv`, so a local `.env` file in the project root is the simplest option.

Start from the provided sample:

```bash
cp .sampleenv .env
```

Then update `.env` with real values for your environment.

## Environment Variables

### Required for local startup

```dotenv
REDIS_HOST=
REDIS_PORT=
REDIS_PASSWORD=

DOCUMENTSERVICE_STREAM_KEY=DOCUMENTSERVICE
DOCUMENTSERVICE_GROUP_NAME=docservice-group
DOCUMENTSERVICE_CONSUMER_NAME_PREFIX=docservice-consumer
DOCUMENTSERVICE_BLOCK_TIME=5000
DOCUMENTSERVICE_BATCH_SIZE=1
DOCUMENTSERVICE_TIMEOUT=3600000

ZIPPER_REDIS_HOST=
ZIPPER_REDIS_PORT=
ZIPPER_REDIS_PASSWORD=
ZIPPER_STREAM_KEY=ZIPPER_STREAM

DOCUMENTSERVICE_DB_HOST=
DOCUMENTSERVICE_DB_NAME=
DOCUMENTSERVICE_DB_PORT=
DOCUMENTSERVICE_DB_USER=
DOCUMENTSERVICE_DB_PASSWORD=

FOI_DB_HOST=
FOI_DB_NAME=
FOI_DB_PORT=
FOI_DB_USER=
FOI_DB_PASSWORD=

DOCUMENTSERVICE_S3_HOST=
DOCUMENTSERVICE_S3_REGION=
DOCUMENTSERVICE_S3_SERVICE=
DOCUMENTSERVICE_S3_ENV=

CDOGS_BASE_URL=
CDOGS_TOKEN_URL=
CDOGS_SERVICE_CLIENT=
CDOGS_SERVICE_CLIENT_SECRET=

HOSTNAME=documentservices-local
```

### Additional variables referenced in code

[`services/documentgenerationservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/services/documentgenerationservice.py) also reads:

```dotenv
OSS_S3_HOST=
OSS_S3_REGION=
```

### Important note about `.sampleenv`

There is currently a mismatch between the sample env file and the active config loader:

- [`.sampleenv`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/.sampleenv) uses `DOCUMENTSERVICE_REDIS_HOST`, `DOCUMENTSERVICE_REDIS_PORT`, and `DOCUMENTSERVICE_REDIS_PASSWORD`
- [`utils/foidocumentserviceconfig.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/utils/foidocumentserviceconfig.py) currently reads `REDIS_HOST`, `REDIS_PORT`, and `REDIS_PASSWORD`

For local execution, set `REDIS_HOST`, `REDIS_PORT`, and `REDIS_PASSWORD` unless the code is updated to align with `.sampleenv`.

## Running Locally

Once the virtual environment is active and `.env` is configured:

```bash
python __main__.py
```

The app will:

- connect to Redis
- create or verify the configured consumer group
- claim stale pending messages
- continuously read new messages from the configured stream

## Running with Docker

### Build the local image

```bash
docker build -f Dockerfile.local -t documentservices:local .
```

### Run the container

```bash
docker run --rm \
  --env-file .env \
  --name documentservices-local \
  documentservices:local
```

If you want a stable consumer name inside Docker, make sure `HOSTNAME` is defined in `.env`.

### BC Gov image variant

This repo also includes [`DockerFile.bcgov`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/DockerFile.bcgov), which uses the BC Gov Python base image:

```bash
docker build -f DockerFile.bcgov -t documentservices:bcgov .
```

## Running Tests

Activate the virtual environment before running tests:

```bash
source .venv/bin/activate
```

Run the default test suite with:

```bash
python -m unittest discover -v
```

Current test behavior:

- [`unittests/test_redactionsummaryservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/unittests/test_redactionsummaryservice.py) is a unit test and should run without external services.
- [`unittests/test_redactionsummary_integration.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/unittests/test_redactionsummary_integration.py) is an integration test for Redis stream publishing.
- The integration test is skipped automatically unless Redis integration environment variables are configured.

Run only the unit test:

```bash
python -m unittest unittests.test_redactionsummaryservice -v
```

Run only the Redis integration test:

```bash
python -m unittest unittests.test_redactionsummary_integration -v
```

To allow the Redis integration test to execute instead of skipping, configure:

```dotenv
DOCUMENTSERVICE_STREAM_KEY=
DOCUMENTSERVICE_REDIS_HOST=
DOCUMENTSERVICE_REDIS_PORT=
DOCUMENTSERVICE_REDIS_PASSWORD=
```

## Architecture Overview

High-level processing flow:

1. A message is read from the Document Service Redis stream.
2. The reader decodes the stream payload and passes it to `redactionsummaryservice`.
3. The summary service:
   - determines whether a summary is required for the message category
   - fetches page flags and template metadata from the database
   - generates summary content
   - renders a PDF through CDOGS
   - uploads the PDF to S3-compatible storage
4. The updated message, including any summary files, is forwarded to the zipper stream.
5. The original Redis message is acknowledged.

Primary components:

- Redis stream consumer: [`rstreamio/reader/documentservicestreamreader.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/rstreamio/reader/documentservicestreamreader.py)
- Summary orchestration: [`services/redactionsummaryservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/services/redactionsummaryservice.py)
- PDF generation: [`services/documentgenerationservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/services/documentgenerationservice.py) and [`services/cdogsapiservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/services/cdogsapiservice.py)
- Storage upload: [`services/s3documentservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/services/s3documentservice.py)
- Downstream publish: [`services/zippingservice.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/services/zippingservice.py)

## Troubleshooting

- Redis connection fails on startup:
  - verify `REDIS_HOST`, `REDIS_PORT`, and `REDIS_PASSWORD`
  - confirm the Redis instance is reachable from your machine or container
- Database connection errors:
  - confirm both Document Service and FOI DB credentials are set
  - verify network access and port reachability
- CDOGS generation errors:
  - verify `CDOGS_BASE_URL`, `CDOGS_TOKEN_URL`, `CDOGS_SERVICE_CLIENT`, and `CDOGS_SERVICE_CLIENT_SECRET`
- S3 upload failures:
  - verify `DOCUMENTSERVICE_S3_*` values
  - verify the database contains the expected `DocumentPathMapper` bucket credentials

## Suggested Next Improvements

- Align [`.sampleenv`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/.sampleenv) with [`utils/foidocumentserviceconfig.py`](/home/alvesfc/workspace/bcgov/foi-modernization/foi-docreviewer/computingservices/DocumentServices/utils/foidocumentserviceconfig.py) so Redis variables are consistent.
- Add a committed `.env.example` that includes the CDOGS and `OSS_S3_*` variables currently missing from `.sampleenv`.
- Add a small `Makefile` or task runner targets for `setup`, `test`, and `run`.
- Add health-check or smoke-test documentation for validating Redis, DB, and CDOGS connectivity before starting the consumer.
