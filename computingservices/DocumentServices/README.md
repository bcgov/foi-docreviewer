# DocumentServices

Generates redaction summary PDFs through CDOGS, uploads them to S3-compatible storage, and forwards document packages to the existing zipper through Redis. This service does not perform generic document conversion.

## Runtime and dependencies

Both `Dockerfile` and `Dockerfile.local` use `python:3.13-bookworm`, the same OS packages, working directory, `app_user`, templates, and entrypoint. Build them as a pair after one base-image pull so verification uses the same resolved base digest.

`requirements.txt` is UTF-8 (previously UTF-16). One source-built PostgreSQL driver, `psycopg2==2.9.10`, replaces overlapping `psycopg2==2.9.5` / `psycopg2-binary==2.8.6` installations. The old driver fails a fresh Python 3.13 import with undefined symbol `_PyInterpreterState_Get`. `marshmallow==3.26.1` replaces `3.0.0rc7`, which imports the removed `distutils` module. Marshmallow remains on major version 3. Other existing dependency pins, including Redis, Walrus, boto3/botocore/s3transfer, wrapt and pycryptodome, are retained. No schema migration or application configuration change is required.

## Local setup

Use Python 3.13 and install `gcc` and `libpq-dev` when working outside Docker:

```bash
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-test.txt
```

Generate local configuration through the sibling local-environment repository; do not copy credentials from deployed environments:

```bash
# From foi-modernization/foi-dev-environment:
set -a
. <(scripts/env-for.sh reviewer-documentservice)
set +a
# Then, from this service directory:
python __main__.py
```

Use `env-for.sh reviewer-documentservice --docker` for a container on the local stack's Docker network. The generated output is shell assignments: source it in a shell, rather than passing it directly as a Docker `--env-file`. Keep generated settings out of version control.

Runtime settings are loaded by [foidocumentserviceconfig.py](utils/foidocumentserviceconfig.py):

- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`; `DOCUMENTSERVICE_STREAM_KEY`, `DOCUMENTSERVICE_GROUP_NAME`, `DOCUMENTSERVICE_CONSUMER_NAME_PREFIX`, and `HOSTNAME`.
- Optional `DOCUMENTSERVICE_BLOCK_TIME`, `DOCUMENTSERVICE_BATCH_SIZE`, `DOCUMENTSERVICE_TIMEOUT` control reads and pending-message claims.
- `ZIPPER_STREAM_KEY` and `ZIPPER_REDIS_*` settings. The existing writer's Walrus client uses the runtime `REDIS_*` connection; retain existing deployment settings.
- `DOCUMENTSERVICE_DB_HOST/NAME/PORT/USER/PASSWORD` and `FOI_DB_HOST/NAME/PORT/USER/PASSWORD` for the two PostgreSQL databases.
- `DOCUMENTSERVICE_S3_HOST/REGION/SERVICE/ENV` and `OSS_S3_HOST/REGION` for object storage.
- `CDOGS_BASE_URL`, `CDOGS_TOKEN_URL`, `CDOGS_SERVICE_CLIENT`, `CDOGS_SERVICE_CLIENT_SECRET`.

The historical `.sampleenv` publisher settings `DOCUMENTSERVICE_REDIS_*` are used by the publisher test; the worker reads `REDIS_*`.

## Building and testing

From this directory:

```bash
docker pull python:3.13-bookworm
docker image inspect python:3.13-bookworm --format '{{json .RepoDigests}}'
docker build --no-cache -t reviewer-documentservice:py313 -f Dockerfile .
docker build --no-cache -t reviewer-documentservice:py313-local -f Dockerfile.local .
docker run --rm --entrypoint python reviewer-documentservice:py313 -m pip check
docker run --rm --entrypoint python -e PYTHONPATH=/home/app_user \
  reviewer-documentservice:py313 integrationtests/runtime_smoke.py
```

Run the complete suite with pytest. `unittest discover` omits the pytest function tests:

```bash
python -m pytest --collect-only -q -p no:cacheprovider unittests
python -m pytest -q -p no:cacheprovider unittests
```

The [CI workflow](../../.github/workflows/documentservices-tests.yml) builds both Dockerfiles and verifies dependency consistency, fresh imports, certificate roots, readable bundled templates and schema construction. It derives disposable test images, installs `requirements-test.txt` only there, runs as `app_user`, and writes pytest artifacts under `/tmp`. A dedicated Redis 7 service enables both Redis tests; CI rejects skipped tests. Require this workflow to pass before merge/promotion, alongside the existing dynamic publishing workflow.

For Redis checks locally, use a disposable Redis instance and explicitly configure both sets of variables:

```bash
export RUN_DOCUMENTSERVICE_REDIS_TESTS=1
export REDIS_HOST=127.0.0.1 REDIS_PORT=6379 REDIS_PASSWORD=''
export DOCUMENTSERVICE_REDIS_HOST="$REDIS_HOST"
export DOCUMENTSERVICE_REDIS_PORT="$REDIS_PORT"
export DOCUMENTSERVICE_REDIS_PASSWORD="$REDIS_PASSWORD"
export DOCUMENTSERVICE_STREAM_KEY=documentservice-local-test-publisher
python -m pytest -q -p no:cacheprovider unittests
```

Never direct these tests at shared dev/test streams. Worker tests create UUID-scoped input/output streams and consumer groups, reclaim a pending message, invoke the real `processmessage`, verify real zipper serialization and acknowledgements, and delete only their own stream keys. Summary generation is isolated from database/CDOGS/S3 in the Redis tests. Separate category tests use real schemas/orchestration with external I/O isolated. HTTP-boundary tests cover CDOGS token requests, cache hits/misses, template upload, hash persistence, render JSON, PDF responses and failures.

These checks characterize the existing failure policy: summary-generation exceptions can still forward original files and acknowledge input. They establish neither exactly-once delivery nor real CDOGS/S3/zipper package success. Production code, group names and recovery behavior are unchanged.
