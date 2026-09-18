# Pipeline End-to-End Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `./e2e/run.sh` Docker Compose harness that pushes sample files through the real File Conversion → Dedupe → Compression → OCRServices binaries and asserts each stage's DB rows, S3 objects, Redis messages and the final ActiveMQ payload.

**Architecture:** One compose file (`e2e/docker-compose.e2e.yml`) starts Postgres (schema from the `api/` Alembic migrations), Redis, SeaweedFS (S3), an nginx record-formats stub, ActiveMQ, the four worker images built from their existing Dockerfiles, and a pytest runner container. The runner seeds S3 + DB the way `request-management-api`/`reviewer_api` would, `XADD`s the flat upload message, then polls each downstream side effect with bounded timeouts.

**Tech Stack:** Docker Compose v2, Python 3.12 + pytest, `psycopg[binary]`, `redis`, `boto3`, `requests`; images `postgres:18`, `redis:7`, `chrislusf/seaweedfs:4.46`, `nginx:1.29.1-alpine`, `apache/activemq-classic:5.18.6`.

**Spec:** `docs/superpowers/specs/2026-09-17-pipeline-e2e-test-design.md`

## Global Constraints

- Nothing in `e2e/` reads the root `.env`; every credential is a test-only literal in the compose file (`foi` / `foi-test`, `redis-test`, S3 `dev`/`dev`, ActiveMQ `admin`/`admin`).
- The pattern to follow is `MCS.FOI.S3FileConversion/docker-compose.integration.yml` + `MCS.FOI.S3FileConversion/integration/run.sh`. Copy its healthchecks and runner shape; do not modify that folder.
- Do not change any service source code. If a worker cannot run under the compose environment, stop and report; the fix belongs in a separate change.
- Bucket is `citz-dev-e` (workers build `{bcgovcode}-{S3_ENV}-e`; test uses `bcgovcode=CITZ`, `*_S3_ENV=dev`). `DocumentPathMapper` row must have `category = 'Records'` for that bucket.
- Stream keys: `e2e-conversion`, `e2e-dedupe`, `e2e-compression`, `e2e-compression-checkpoint`, `e2e-pagecount`; OCR stream is fixed at `foi:ocr` (OCRServices requires prefix `foi`, topic `ocr`).
- Every wait is bounded by `E2E_STAGE_TIMEOUT` (default 120 s) and fails with the last observed state in the message.
- Commit after each task. Working tree already contains unrelated user changes and untracked IDE folders — `git add` only the paths named in each task.

---

## File map

| Path | Responsibility |
| --- | --- |
| `e2e/README.md` | how to run, what is asserted, how to add a sample |
| `e2e/run.sh` | compose up/down wrapper, log capture, exit code |
| `e2e/docker-compose.e2e.yml` | all services |
| `e2e/.gitignore` | ignores `TestResults/` |
| `e2e/samples/simple-test-doc.docx`, `e2e/samples/sample.pdf` | inputs |
| `e2e/fixtures/nginx.conf`, `e2e/fixtures/record-formats.json`, `e2e/fixtures/seaweedfs/config.json` | stubs |
| `e2e/tests/Dockerfile`, `e2e/tests/requirements.txt`, `e2e/tests/pytest.ini` | runner image |
| `e2e/tests/settings.py` | env → `Settings` dataclass |
| `e2e/tests/clients.py` | Postgres/Redis/S3/ActiveMQ helpers + `wait_until` |
| `e2e/tests/seed.py` | DB seed functions mirroring request-management-api |
| `e2e/tests/stages.py` | one `wait_for_*` function per pipeline stage |
| `e2e/tests/conftest.py` | fixtures wiring the above |
| `e2e/tests/test_readiness.py` | infra + consumer-group readiness |
| `e2e/tests/test_pdf_pipeline.py` | dedupe → compression → OCR |
| `e2e/tests/test_docx_pipeline.py` | conversion → dedupe → compression → OCR |
| `e2e/tests/test_duplicate.py` | same PDF twice → same hash |

---

### Task 1: Scaffold `e2e/` with samples, fixtures and gitignore

**Files:**
- Create: `e2e/.gitignore`, `e2e/samples/simple-test-doc.docx`, `e2e/samples/sample.pdf`, `e2e/fixtures/nginx.conf`, `e2e/fixtures/record-formats.json`, `e2e/fixtures/seaweedfs/config.json`

**Interfaces:**
- Produces: sample paths mounted at `/samples` in the runner (Task 3); fixtures mounted by compose (Task 2).

- [ ] **Step 1: Copy samples and fixtures**

```bash
mkdir -p e2e/samples e2e/fixtures/seaweedfs e2e/tests
cp MCS.FOI.S3FileConversion/MCS.FOI.DocToPDFUnitTests/SourceFiles/simple-test-doc.docx e2e/samples/
cp computingservices/DedupeServices/unittests/files/sample.pdf e2e/samples/
cp MCS.FOI.S3FileConversion/integration/seaweedfs/config.json e2e/fixtures/seaweedfs/config.json
printf 'TestResults/\n' > e2e/.gitignore
```

- [ ] **Step 2: Write `e2e/fixtures/record-formats.json`**

```json
{"conversion":[".doc",".docx",".xls",".xlsx",".ppt",".pptx",".msg",".eml",".ics"],"dedupe":[".pdf",".jpg",".jpeg",".png"],"nonredactable":[]}
```

- [ ] **Step 3: Write `e2e/fixtures/nginx.conf`**

```nginx
events {}

http {
    server {
        listen 80;

        location = /healthz {
            access_log off;
            default_type text/plain;
            return 200 "ok\n";
        }

        location = /formats.json {
            default_type application/json;
            alias /usr/share/nginx/html/record-formats.json;
        }
    }
}
```

- [ ] **Step 4: Verify the sample PDF has no attachments (Dedupe raises on attachments)**

Run: `python3 -c "import zlib,re;d=open('e2e/samples/sample.pdf','rb').read();print('EmbeddedFiles' in str(d), b'/FileAttachment' in d)"`
Expected: `False False`

- [ ] **Step 5: Commit**

```bash
git add e2e/.gitignore e2e/samples e2e/fixtures
git commit -m "test(e2e): scaffold pipeline e2e folder with samples and fixtures"
```

---

### Task 2: Infrastructure compose services, DB migration and `run.sh`

**Files:**
- Create: `e2e/docker-compose.e2e.yml`, `e2e/run.sh`

**Interfaces:**
- Produces: service hostnames `postgres:5432` (db `docreviewerdb`, user `foi`, pw `foi-test`), `redis:6379` (pw `redis-test`), `seaweedfs:8333` (S3 keys `dev`/`dev`), `record-formats:80`, `activemq:8161` (REST `admin`/`admin`, queue `foidococr`); a completed `db-migrate` one-shot.

- [ ] **Step 1: Write `e2e/docker-compose.e2e.yml` (infra only)**

```yaml
services:
  postgres:
    image: postgres:18
    environment:
      POSTGRES_DB: docreviewerdb
      POSTGRES_USER: foi
      POSTGRES_PASSWORD: foi-test
    volumes:
      - postgres-data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U foi -d docreviewerdb"]
      interval: 2s
      timeout: 3s
      retries: 15

  db-migrate:
    build:
      context: ../api
      dockerfile: dockerfile.local
    entrypoint: ["python", "manage.py", "db", "upgrade"]
    environment:
      FLASK_ENV: testing
      DATABASE_TEST_URL: postgresql://foi:foi-test@postgres:5432/docreviewerdb
    depends_on:
      postgres:
        condition: service_healthy

  redis:
    image: redis:7
    command: ["redis-server", "--requirepass", "redis-test"]
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis-test", "ping"]
      interval: 2s
      timeout: 3s
      retries: 15

  seaweedfs:
    image: chrislusf/seaweedfs:4.46
    command:
      - server
      - -dir=/data
      - -s3
      - -s3.port=8333
      - -s3.config=/etc/seaweedfs/config.json
      - -volume.max=100
      - -master.volumeSizeLimitMB=100
      - -master.volumePreallocate=false
    volumes:
      - seaweedfs-data:/data
      - ./fixtures/seaweedfs/config.json:/etc/seaweedfs/config.json:ro
    healthcheck:
      test:
        - CMD-SHELL
        - >-
          wget -qO- http://127.0.0.1:9333/dir/status |
          grep -q '"DataNodes":\[{' &&
          wget -q --spider http://127.0.0.1:8333/healthz
      interval: 5s
      timeout: 3s
      retries: 60
      start_period: 10s

  record-formats:
    image: nginx:1.29.1-alpine
    volumes:
      - ./fixtures/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./fixtures/record-formats.json:/usr/share/nginx/html/record-formats.json:ro
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://127.0.0.1/healthz"]
      interval: 2s
      timeout: 3s
      retries: 15

  activemq:
    image: apache/activemq-classic:5.18.6
    environment:
      ACTIVEMQ_CONNECTION_USER: admin
      ACTIVEMQ_CONNECTION_PASSWORD: admin
      ACTIVEMQ_WEB_USER: admin
      ACTIVEMQ_WEB_PASSWORD: admin
    healthcheck:
      # The image is Ubuntu/Temurin based and ships curl; if the check reports
      # "curl: not found", switch to: bash -c 'exec 3<>/dev/tcp/127.0.0.1/8161'
      test: ["CMD-SHELL", "curl -fsu admin:admin http://127.0.0.1:8161/api/jolokia/version >/dev/null"]
      interval: 5s
      timeout: 5s
      retries: 30
      start_period: 15s

volumes:
  postgres-data:
  seaweedfs-data:
```

- [ ] **Step 2: Bring up infra and check `db-migrate`**

Run:
```bash
cd e2e && docker compose -p e2e-probe -f docker-compose.e2e.yml up --build -d --wait postgres redis seaweedfs record-formats activemq && \
docker compose -p e2e-probe -f docker-compose.e2e.yml run --rm db-migrate; echo "exit=$?"
```
Expected: `exit=0` and Alembic output ending in the latest revision.

If `db-migrate` fails because `create_app()` needs something else (e.g. a Redis URL or JWT variable), add the missing variable with a harmless literal to the `db-migrate` `environment:` block and rerun. Do not edit `api/`.

If it cannot be made to run at all, fall back: run the migrations once from a working root Compose stack, then `pg_dump --schema-only --no-owner --no-privileges -U foi docreviewerdb > e2e/fixtures/schema.sql`, mount it at `/docker-entrypoint-initdb.d/001-schema.sql:ro` on `postgres`, delete the `db-migrate` service, and replace every later `db-migrate: condition: service_completed_successfully` with `postgres: condition: service_healthy`.

- [ ] **Step 3: Verify the tables the workers need exist**

Run:
```bash
docker compose -p e2e-probe -f docker-compose.e2e.yml exec postgres psql -U foi -d docreviewerdb -tAc \
 "select string_agg(table_name, ',') from information_schema.tables where table_name in ('DocumentPathMapper','DocumentMaster','DocumentAttributes','FileConversionJob','DeduplicationJob','Documents','DocumentHashCodes','CompressionJob','PageCalculatorJob','OCRActiveMQJob','DocumentDeleted')"
```
Expected: all 11 names in the output.

- [ ] **Step 4: Verify ActiveMQ REST is reachable from another container**

Run:
```bash
docker compose -p e2e-probe -f docker-compose.e2e.yml run --rm --entrypoint sh record-formats -c \
 'wget -qO- --header="Authorization: Basic YWRtaW46YWRtaW4=" "http://activemq:8161/api/message/e2eprobe?type=queue&oneShot=true&timeout=1000"; echo " status=$?"'
```
Expected: `status=0` (HTTP 204 for an empty queue is success; wget prints nothing).

If it fails with connection refused, the Jetty console is bound to `127.0.0.1` inside the container. Fix by extracting and overriding the config: `docker cp $(docker compose -p e2e-probe -f docker-compose.e2e.yml ps -q activemq):/opt/apache-activemq/conf/jetty.xml e2e/fixtures/activemq/jetty.xml`, change the `host` property value to `0.0.0.0`, and mount it at `/opt/apache-activemq/conf/jetty.xml:ro` on the `activemq` service. Rerun the probe.

- [ ] **Step 5: Tear down the probe stack**

Run: `docker compose -p e2e-probe -f docker-compose.e2e.yml down --volumes --remove-orphans`

- [ ] **Step 6: Write `e2e/run.sh`**

```bash
#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose_file="${E2E_COMPOSE_FILE:-$script_dir/docker-compose.e2e.yml}"
run_id="${GITHUB_RUN_ID:-local}"
project_name="foi-pipeline-e2e-${run_id}-$$"
results_dir="$script_dir/TestResults"
mkdir -p "$results_dir"

compose=(docker compose --project-name "$project_name" --file "$compose_file")

cleanup() {
    local original_status=$?
    trap - EXIT
    set +e

    {
        "${compose[@]}" ps
        "${compose[@]}" logs --no-color
    } >"$results_dir/compose.log" 2>&1

    if (( original_status != 0 )); then
        printf 'Pipeline e2e test failed; Compose diagnostics follow:\n' >&2
        cat "$results_dir/compose.log" >&2
    fi

    "${compose[@]}" down --volumes --remove-orphans
    exit "$original_status"
}
trap cleanup EXIT

cd "$script_dir"
"${compose[@]}" up --build --abort-on-container-exit --exit-code-from e2e-tests "$@"
```

Run: `chmod +x e2e/run.sh && bash -n e2e/run.sh && echo syntax-ok`
Expected: `syntax-ok`

- [ ] **Step 7: Commit**

```bash
git add e2e/docker-compose.e2e.yml e2e/run.sh e2e/fixtures
git commit -m "test(e2e): add infrastructure compose services and runner script"
```

---

### Task 3: Test-runner image, settings, clients and readiness test

**Files:**
- Create: `e2e/tests/Dockerfile`, `e2e/tests/requirements.txt`, `e2e/tests/pytest.ini`, `e2e/tests/settings.py`, `e2e/tests/clients.py`, `e2e/tests/conftest.py`, `e2e/tests/test_readiness.py`
- Modify: `e2e/docker-compose.e2e.yml` (add `e2e-tests` service)

**Interfaces:**
- Produces:
  - `settings.Settings` dataclass, `settings.load() -> Settings`
  - `clients.wait_until(predicate: Callable[[], T | None], timeout: float, interval: float = 0.5, describe: Callable[[], str] | None = None) -> T`
  - `clients.Postgres(dsn)` with `.one(sql, params) -> tuple | None`, `.all(sql, params) -> list[tuple]`, `.execute(sql, params) -> None`
  - `clients.Redis(url)` with `.xadd(stream, fields: dict[str, str]) -> str`, `.entries(stream, count=200) -> list[tuple[str, dict[str, str]]]`, `.has_group(stream, group) -> bool`
  - `clients.S3(settings)` with `.ensure_bucket()`, `.put(key, path, content_type)`, `.get(key) -> bytes`, `.exists(key) -> bool`, `.url(key) -> str`
  - `clients.ActiveMQ(settings)` with `.consume_one(timeout_ms=2000) -> dict | None`
  - pytest fixtures: `settings`, `pg`, `redis_client`, `s3`, `activemq`, `samples_dir`

- [ ] **Step 1: Write `e2e/tests/requirements.txt`**

```
pytest==8.3.3
psycopg[binary]==3.2.3
redis==5.2.0
boto3==1.35.36
requests==2.32.3
```

- [ ] **Step 2: Write `e2e/tests/pytest.ini`**

```ini
[pytest]
addopts = -ra -p no:cacheprovider --junitxml=/test-results/junit.xml
testpaths = .
```

- [ ] **Step 3: Write `e2e/tests/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /tests
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENTRYPOINT ["pytest"]
```

- [ ] **Step 4: Write `e2e/tests/settings.py`**

```python
"""Runtime configuration for the pipeline e2e tests, read from environment."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_dsn: str
    redis_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    conversion_stream: str
    conversion_group: str
    dedupe_stream: str
    dedupe_group: str
    compression_stream: str
    pagecount_stream: str
    ocr_stream: str
    ocr_group: str
    activemq_url: str
    activemq_user: str
    activemq_password: str
    activemq_queue: str
    stage_timeout: float
    samples_dir: str
    bcgovcode: str = "CITZ"


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required; run through ./e2e/run.sh")
    return value


def load() -> Settings:
    return Settings(
        db_dsn=_require("E2E_DB_DSN"),
        redis_url=_require("E2E_REDIS_URL"),
        s3_endpoint=_require("E2E_S3_ENDPOINT"),
        s3_access_key=_require("E2E_S3_ACCESS_KEY"),
        s3_secret_key=_require("E2E_S3_SECRET_KEY"),
        s3_bucket=_require("E2E_S3_BUCKET"),
        conversion_stream=_require("E2E_CONVERSION_STREAM"),
        conversion_group=_require("E2E_CONVERSION_GROUP"),
        dedupe_stream=_require("E2E_DEDUPE_STREAM"),
        dedupe_group=_require("E2E_DEDUPE_GROUP"),
        compression_stream=_require("E2E_COMPRESSION_STREAM"),
        pagecount_stream=_require("E2E_PAGECOUNT_STREAM"),
        ocr_stream=_require("E2E_OCR_STREAM"),
        ocr_group=_require("E2E_OCR_GROUP"),
        activemq_url=_require("E2E_ACTIVEMQ_URL"),
        activemq_user=_require("E2E_ACTIVEMQ_USER"),
        activemq_password=_require("E2E_ACTIVEMQ_PASSWORD"),
        activemq_queue=_require("E2E_ACTIVEMQ_QUEUE"),
        stage_timeout=float(os.environ.get("E2E_STAGE_TIMEOUT", "120")),
        samples_dir=os.environ.get("E2E_SAMPLES_DIR", "/samples"),
    )
```

- [ ] **Step 5: Write `e2e/tests/clients.py`**

```python
"""Thin clients over Postgres, Redis, S3 and ActiveMQ plus a bounded poller."""
from __future__ import annotations

import json
import time
from typing import Callable, TypeVar

import boto3
import psycopg
import redis as redis_lib
import requests
from botocore.config import Config
from botocore.exceptions import ClientError

from settings import Settings

T = TypeVar("T")


class StageTimeout(AssertionError):
    pass


def wait_until(
    predicate: Callable[[], T | None],
    timeout: float,
    interval: float = 0.5,
    describe: Callable[[], str] | None = None,
) -> T:
    """Poll predicate until it returns a truthy value or timeout elapses."""
    deadline = time.monotonic() + timeout
    while True:
        result = predicate()
        if result:
            return result
        if time.monotonic() >= deadline:
            detail = describe() if describe else "no detail"
            raise StageTimeout(f"timed out after {timeout:.0f}s; last state: {detail}")
        time.sleep(interval)


class Postgres:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def one(self, sql: str, params: tuple = ()) -> tuple | None:
        with psycopg.connect(self._dsn) as conn:
            return conn.execute(sql, params).fetchone()

    def all(self, sql: str, params: tuple = ()) -> list[tuple]:
        with psycopg.connect(self._dsn) as conn:
            return conn.execute(sql, params).fetchall()

    def execute(self, sql: str, params: tuple = ()) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(sql, params)
            conn.commit()


class Redis:
    def __init__(self, url: str) -> None:
        self._r = redis_lib.Redis.from_url(url, decode_responses=True)

    def ping(self) -> bool:
        return bool(self._r.ping())

    def xadd(self, stream: str, fields: dict[str, str]) -> str:
        return self._r.xadd(stream, fields)

    def entries(self, stream: str, count: int = 200) -> list[tuple[str, dict[str, str]]]:
        """Newest-first entries; the typed OCR stream keeps its JSON in `payload`."""
        return self._r.xrevrange(stream, count=count)

    def has_group(self, stream: str, group: str) -> bool:
        try:
            return any(g["name"] == group for g in self._r.xinfo_groups(stream))
        except redis_lib.ResponseError as error:
            if "no such key" in str(error).lower():
                return False
            raise


class S3:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._endpoint = settings.s3_endpoint
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
            config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.create_bucket(Bucket=self._bucket)
        except ClientError as error:
            if error.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
                raise

    def put(self, key: str, path: str, content_type: str) -> None:
        with open(path, "rb") as handle:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=handle, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as error:
            if error.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def url(self, key: str) -> str:
        """The path-style URL workers receive in `s3filepath`."""
        return f"{self._endpoint}/{self._bucket}/{key}"


class ActiveMQ:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.activemq_url
        self._auth = (settings.activemq_user, settings.activemq_password)
        self._queue = settings.activemq_queue

    def reachable(self) -> bool:
        response = requests.get(
            f"{self._url}/{self._queue}",
            params={"type": "queue", "oneShot": "true", "timeout": "200"},
            auth=self._auth,
            timeout=5,
        )
        return response.status_code in (200, 204)

    def consume_one(self, timeout_ms: int = 2000) -> dict | None:
        """Consume and return the next JSON message on the queue, or None."""
        response = requests.get(
            f"{self._url}/{self._queue}",
            params={"type": "queue", "oneShot": "true", "timeout": str(timeout_ms)},
            auth=self._auth,
            timeout=(timeout_ms / 1000) + 5,
        )
        if response.status_code == 204 or not response.text.strip():
            return None
        response.raise_for_status()
        return json.loads(response.text)
```

- [ ] **Step 6: Write `e2e/tests/conftest.py`**

```python
from __future__ import annotations

import pytest

import clients
import settings as settings_module


@pytest.fixture(scope="session")
def settings() -> settings_module.Settings:
    return settings_module.load()


@pytest.fixture(scope="session")
def pg(settings) -> clients.Postgres:
    return clients.Postgres(settings.db_dsn)


@pytest.fixture(scope="session")
def redis_client(settings) -> clients.Redis:
    return clients.Redis(settings.redis_url)


@pytest.fixture(scope="session")
def s3(settings) -> clients.S3:
    client = clients.S3(settings)
    client.ensure_bucket()
    return client


@pytest.fixture(scope="session")
def activemq(settings) -> clients.ActiveMQ:
    return clients.ActiveMQ(settings)


@pytest.fixture(scope="session")
def samples_dir(settings) -> str:
    return settings.samples_dir
```

- [ ] **Step 7: Write `e2e/tests/test_readiness.py`**

```python
"""Fails fast with a clear message when the stack itself is not ready."""
from __future__ import annotations

import os

REQUIRED_TABLES = {
    "DocumentPathMapper", "DocumentMaster", "DocumentAttributes", "FileConversionJob",
    "DeduplicationJob", "Documents", "DocumentHashCodes", "CompressionJob",
    "PageCalculatorJob", "OCRActiveMQJob",
}


def test_database_has_pipeline_tables(pg):
    rows = pg.all(
        "select table_name from information_schema.tables where table_schema = 'public'"
    )
    present = {row[0] for row in rows}
    missing = REQUIRED_TABLES - present
    assert not missing, f"missing tables: {sorted(missing)}"


def test_redis_is_reachable(redis_client):
    assert redis_client.ping()


def test_s3_bucket_exists(s3, settings):
    s3.put("readiness/ping.txt", os.path.join(os.path.dirname(__file__), "requirements.txt"), "text/plain")
    assert s3.exists("readiness/ping.txt")


def test_activemq_rest_is_reachable(activemq):
    assert activemq.reachable()


def test_samples_are_mounted(samples_dir):
    assert os.path.isfile(os.path.join(samples_dir, "simple-test-doc.docx"))
    assert os.path.isfile(os.path.join(samples_dir, "sample.pdf"))
```

- [ ] **Step 8: Add the `e2e-tests` service to `e2e/docker-compose.e2e.yml`**

Append under `services:` (before `volumes:`):

```yaml
  e2e-tests:
    build:
      context: ./tests
    environment:
      E2E_DB_DSN: postgresql://foi:foi-test@postgres:5432/docreviewerdb
      E2E_REDIS_URL: redis://:redis-test@redis:6379/0
      E2E_S3_ENDPOINT: http://seaweedfs:8333
      E2E_S3_ACCESS_KEY: dev
      E2E_S3_SECRET_KEY: dev
      E2E_S3_BUCKET: citz-dev-e
      E2E_CONVERSION_STREAM: e2e-conversion
      E2E_CONVERSION_GROUP: file-conversion-consumer-group
      E2E_DEDUPE_STREAM: e2e-dedupe
      E2E_DEDUPE_GROUP: dedupe
      E2E_COMPRESSION_STREAM: e2e-compression
      E2E_PAGECOUNT_STREAM: e2e-pagecount
      E2E_OCR_STREAM: foi:ocr
      E2E_OCR_GROUP: foi-ocr
      E2E_ACTIVEMQ_URL: http://activemq:8161/api/message
      E2E_ACTIVEMQ_USER: admin
      E2E_ACTIVEMQ_PASSWORD: admin
      E2E_ACTIVEMQ_QUEUE: foidococr
      E2E_STAGE_TIMEOUT: "120"
      E2E_SAMPLES_DIR: /samples
    volumes:
      - ./samples:/samples:ro
      - ./TestResults:/test-results
    depends_on:
      db-migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
      seaweedfs:
        condition: service_healthy
      record-formats:
        condition: service_healthy
      activemq:
        condition: service_healthy
```

- [ ] **Step 9: Run the harness with only the readiness tests**

Run: `./e2e/run.sh`
Expected: 5 passed, exit 0, `e2e/TestResults/junit.xml` and `compose.log` present.

- [ ] **Step 10: Commit**

```bash
git add e2e/tests e2e/docker-compose.e2e.yml
git commit -m "test(e2e): add pytest runner with settings, clients and readiness checks"
```

---

### Task 4: Worker services in compose + consumer-group readiness

**Files:**
- Modify: `e2e/docker-compose.e2e.yml` (add `file-conversion`, `dedupe`, `compression`, `ocr`; extend `e2e-tests.depends_on`)
- Modify: `e2e/tests/test_readiness.py`

**Interfaces:**
- Produces: consumer groups `file-conversion-consumer-group` on `e2e-conversion`, `dedupe` on `e2e-dedupe`, `foi-ocr` on `foi:ocr`. (Legacy compression has no group; it polls `e2e-compression` from `e2e-compression-checkpoint`.)

- [ ] **Step 1: Add the four worker services**

Insert under `services:`:

```yaml
  file-conversion:
    build:
      context: ../MCS.FOI.S3FileConversion
      dockerfile: Dockerfile
    environment:
      DATABASE_HOST: postgres
      DATABASE_PORT: "5432"
      DATABASE_NAME: docreviewerdb
      DATABASE_USERNAME: foi
      DATABASE_PASSWORD: foi-test
      REDIS_STREAM_HOST: redis
      REDIS_STREAM_PORT: "6379"
      REDIS_STREAM_PASSWORD: redis-test
      REDIS_STREAM_KEY: e2e-conversion
      DEDUPE_STREAM_KEY: e2e-dedupe
      REDIS_STREAM_CONSUMER_GROUP: file-conversion-consumer-group
      CONSUMER_NAME: e2e-worker
      S3_HOST: http://seaweedfs:8333
      RECORD_FORMATS: http://record-formats/formats.json
      FILE_CONVERSION_SYNCFUSIONKEY: ""
      FILE_CONVERSION_FAILTUREATTEMPT: "1"
      FILE_CONVERSION_WAITTIME: "1"
      FILE_CONVERSION_OPENFILE_WAITTIME: "5"
      FILE_CONVERSION_CLAIM_MIN_IDLE_MINUTES: "150"
      FILE_CONVERSION_CLAIM_INTERVAL_SECONDS: "30"
      FILE_CONVERSION_MAX_DELIVERY_ATTEMPTS: "3"
      FILE_CONVERSION_DLQ_STREAM_KEY: ""
      FILE_CONVERSION_DLQ_MAX_LENGTH: "10000"
    depends_on:
      db-migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
      seaweedfs:
        condition: service_healthy
      record-formats:
        condition: service_healthy

  dedupe:
    build:
      context: ../computingservices/DedupeServices
      dockerfile: Dockerfile
    environment:
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      REDIS_PASSWORD: redis-test
      DEDUPE_STREAM_KEY: e2e-dedupe
      DEDUPE_CONSUMER_GROUP: dedupe
      DEDUPE_CONSUMER_NAME: e2e-dedupe-1
      DEDUPE_DB_HOST: postgres
      DEDUPE_DB_PORT: "5432"
      DEDUPE_DB_NAME: docreviewerdb
      DEDUPE_DB_USER: foi
      DEDUPE_DB_PASSWORD: foi-test
      DEDUPE_S3_HOST: seaweedfs:8333
      DEDUPE_S3_REGION: us-east-1
      DEDUPE_S3_SERVICE: s3
      DEDUPE_S3_ENV: dev
      DEDUPE_REQUEST_MANAGEMENT_API: http://record-formats
      DEDUPE_RECORD_FORMATS: http://record-formats/formats.json
      PAGECALCULATOR_STREAM_KEY: e2e-pagecount
      COMPRESSION_MESSAGING_MODE: ${COMPRESSION_MESSAGING_MODE:-legacy}
      COMPRESSION_STREAM_KEY: e2e-compression
      COMPRESSION_TOPIC: compression
      COMPRESSION_WORKLOAD: normal
      MESSAGING_STREAM_PREFIX: foi
      NOTIFICATION_STREAM_KEY: e2e-notifications
      HEALTH_CHECK_INTERVAL: "15"
    depends_on:
      db-migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
      seaweedfs:
        condition: service_healthy
      record-formats:
        condition: service_healthy

  compression:
    build:
      context: ../computingservices/CompressionServices
      dockerfile: Dockerfile
    environment:
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      REDIS_PASSWORD: redis-test
      REDIS_CONSUMER_NAME: e2e-compression-1
      COMPRESSION_MESSAGING_MODE: ${COMPRESSION_MESSAGING_MODE:-legacy}
      COMPRESSION_WORKLOAD: normal
      COMPRESSION_PROCESSING_TIMEOUT: 2m
      MESSAGING_STREAM_PREFIX: foi
      COMPRESSION_TOPIC: compression
      OCR_TOPIC: ocr
      MESSAGING_CONSUMER_GROUP: foi-compression-normal
      MESSAGING_CLAIM_INTERVAL: 30s
      MESSAGING_CLAIM_MIN_IDLE: 3m
      MESSAGING_MAX_DELIVERY_ATTEMPTS: "3"
      MESSAGING_SHUTDOWN_TIMEOUT: 25s
      COMPRESSION_STREAM_KEY: e2e-compression
      COMPRESSION_CHECKPOINT_KEY: e2e-compression-checkpoint
      COMPRESSION_DB_HOST: postgres
      COMPRESSION_DB_PORT: "5432"
      COMPRESSION_DB_NAME: docreviewerdb
      COMPRESSION_DB_USER: foi
      COMPRESSION_DB_PASSWORD: foi-test
      COMPRESSION_S3_HOST: http://seaweedfs:8333
      COMPRESSION_S3_REGION: us-east-1
      COMPRESSION_S3_SERVICE: s3
      COMPRESSION_S3_ENV: dev
      COMPRESSION_REQUEST_MANAGEMENT_API: http://record-formats
      COMPRESSION_RECORD_FORMATS: http://record-formats/formats.json
      NOTIFICATION_STREAM_KEY: e2e-notifications
      HEALTH_CHECK_INTERVAL: "15"
    depends_on:
      db-migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
      seaweedfs:
        condition: service_healthy

  ocr:
    build:
      context: ../computingservices/OCRServices
      dockerfile: Dockerfile
    environment:
      LOG_LEVEL: INFO
      REDIS_HOST: redis
      REDIS_PORT: "6379"
      REDIS_PASSWORD: redis-test
      MESSAGING_STREAM_PREFIX: foi
      OCR_TOPIC: ocr
      MESSAGING_CONSUMER_GROUP: foi-ocr
      OCR_CONSUMER_NAME: e2e-ocr-1
      MESSAGING_CLAIM_INTERVAL: 30s
      MESSAGING_CLAIM_MIN_IDLE: 3m
      MESSAGING_MAX_DELIVERY_ATTEMPTS: "3"
      MESSAGING_SHUTDOWN_TIMEOUT: 30s
      OCR_PROCESSING_TIMEOUT: 1m
      OCR_DB_HOST: postgres
      OCR_DB_PORT: "5432"
      OCR_DB_USER: foi
      OCR_DB_PASSWORD: foi-test
      OCR_DB_NAME: docreviewerdb
      ACTIVEMQ_URL: http://activemq:8161/api/message
      ACTIVEMQ_USERNAME: admin
      ACTIVEMQ_PASSWORD: admin
      ACTIVEMQ_DESTINATION: foidococr
      NOTIFICATION_STREAM_KEY: e2e-notifications
    depends_on:
      db-migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
      activemq:
        condition: service_healthy
```

Then add to `e2e-tests.depends_on`:

```yaml
      file-conversion:
        condition: service_started
      dedupe:
        condition: service_started
      compression:
        condition: service_started
      ocr:
        condition: service_started
```

- [ ] **Step 2: Add consumer-group readiness assertions to `e2e/tests/test_readiness.py`**

Append:

```python
from clients import wait_until


def test_workers_registered_consumer_groups(redis_client, settings):
    expected = [
        (settings.conversion_stream, settings.conversion_group),
        (settings.dedupe_stream, settings.dedupe_group),
        (settings.ocr_stream, settings.ocr_group),
    ]
    for stream, group in expected:
        wait_until(
            lambda: redis_client.has_group(stream, group),
            timeout=settings.stage_timeout,
            describe=lambda: f"group {group!r} not yet on stream {stream!r}",
        )
```

- [ ] **Step 3: Run the harness; expect readiness to pass and all workers to stay up**

Run: `./e2e/run.sh`
Expected: 6 passed, exit 0.

If a worker exits on startup, read its lines in `e2e/TestResults/compose.log`. Typical causes and fixes (compose-only, no source changes):
- Compression `config` validation error → adjust the named variable (e.g. `MESSAGING_CLAIM_MIN_IDLE` must exceed `COMPRESSION_PROCESSING_TIMEOUT`).
- Dedupe `KeyError`/`None` for a config var → add the variable listed in `computingservices/DedupeServices/utils/foidedupeconfig.py`.
- Go modules failing to download during `docker build` → build once with network: `docker compose -f e2e/docker-compose.e2e.yml build compression ocr`.

- [ ] **Step 4: Commit**

```bash
git add e2e/docker-compose.e2e.yml e2e/tests/test_readiness.py
git commit -m "test(e2e): run conversion, dedupe, compression and ocr workers in the e2e stack"
```

---

### Task 5: Seeding, stage waits, and the PDF pipeline test

**Files:**
- Create: `e2e/tests/seed.py`, `e2e/tests/stages.py`, `e2e/tests/test_pdf_pipeline.py`

**Interfaces:**
- Produces:
  - `seed.Ids` dataclass (`ministryrequestid`, `documentmasterid`, `jobid`, `batch`, `requestnumber`) and `seed.new_ids(prefix: int) -> Ids`
  - `seed.ensure_path_mapper(pg, bucket)`
  - `seed.seed_pdf_upload(pg, ids, s3url, filename, filesize)`
  - `seed.seed_docx_upload(pg, ids, s3url, filename, filesize)`
  - `seed.upload_message(ids, s3url, filename, filesize, extension) -> dict[str, str]`
  - `stages.wait_for_dedupe(pg, redis, settings, ids) -> DedupeResult(documentid, rank1hash, compressionjobid)`
  - `stages.wait_for_conversion(pg, s3, redis, settings, ids) -> ConversionResult(outputdocumentmasterid, pdf_url)`
  - `stages.wait_for_compression(pg, s3, settings, ids, compressionjobid) -> CompressionResult(status, compressedfilepath)`
  - `stages.wait_for_ocr_dispatch(pg, redis, activemq, settings, ids, compressionjobid) -> dict` (the ActiveMQ payload)

- [ ] **Step 1: Write `e2e/tests/seed.py`**

```python
"""Rows request-management-api / reviewer_api create before publishing work."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from clients import Postgres


@dataclass(frozen=True)
class Ids:
    ministryrequestid: int
    documentmasterid: int
    jobid: int
    batch: str
    requestnumber: str


def new_ids(prefix: int) -> Ids:
    """Unique ids per test run; prefix separates tests inside one run."""
    seq = int(time.time()) % 100000
    base = prefix * 1_000_000 + seq
    return Ids(
        ministryrequestid=base,
        documentmasterid=base,
        jobid=base,
        batch=f"e2e-batch-{base}",
        requestnumber=f"FOI-E2E-{base}",
    )


def ensure_path_mapper(pg: Postgres, bucket: str) -> None:
    """Workers look up S3 keys by bucket; Dedupe/Compression require category 'Records'."""
    pg.execute(
        '''INSERT INTO "DocumentPathMapper" (category, bucket, attributes, isactive, createdby)
           SELECT 'Records', %s, '{"s3accesskey":"dev","s3secretkey":"dev"}', true, 'e2e'
           WHERE NOT EXISTS (SELECT 1 FROM "DocumentPathMapper" WHERE bucket = %s AND category = 'Records')''',
        (bucket, bucket),
    )


def _seed_document(pg: Postgres, ids: Ids, s3url: str, filename: str, filesize: int, extension: str) -> None:
    pg.execute(
        '''INSERT INTO "DocumentMaster" (documentmasterid, filepath, ministryrequestid, isredactionready, createdby)
           VALUES (%s, %s, %s, false, 'e2e')''',
        (ids.documentmasterid, s3url, ids.ministryrequestid),
    )
    pg.execute(
        '''INSERT INTO "DocumentAttributes" (version, documentmasterid, attributes, createdby, isactive)
           VALUES (1, %s, %s, '{"user":"e2e"}', true)''',
        (ids.documentmasterid, json.dumps({"filesize": filesize, "extension": extension, "incompatible": False})),
    )


def seed_pdf_upload(pg: Postgres, ids: Ids, s3url: str, filename: str, filesize: int) -> None:
    _seed_document(pg, ids, s3url, filename, filesize, ".pdf")
    pg.execute(
        '''INSERT INTO "DeduplicationJob"
           (deduplicationjobid, version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status)
           VALUES (%s, 1, %s, %s, 'rank1', 'recordupload', %s, %s, 'pushedtostream')''',
        (ids.jobid, ids.ministryrequestid, ids.batch, ids.documentmasterid, filename),
    )


def seed_docx_upload(pg: Postgres, ids: Ids, s3url: str, filename: str, filesize: int) -> None:
    _seed_document(pg, ids, s3url, filename, filesize, ".docx")
    pg.execute(
        '''INSERT INTO "FileConversionJob"
           (fileconversionjobid, version, ministryrequestid, batch, trigger, inputdocumentmasterid, filename, status)
           VALUES (%s, 1, %s, %s, 'recordupload', %s, %s, 'pushedtostream')''',
        (ids.jobid, ids.ministryrequestid, ids.batch, ids.documentmasterid, filename),
    )


def upload_message(ids: Ids, s3url: str, filename: str, filesize: int, extension: str) -> dict[str, str]:
    """The flat field map request-management-api publishes to conversion or dedupe."""
    return {
        "s3filepath": s3url,
        "requestnumber": ids.requestnumber,
        "bcgovcode": "CITZ",
        "filename": filename,
        "ministryrequestid": str(ids.ministryrequestid),
        "attributes": json.dumps({"filesize": filesize, "extension": extension, "incompatible": False}),
        "batch": ids.batch,
        "jobid": str(ids.jobid),
        "documentmasterid": str(ids.documentmasterid),
        "trigger": "recordupload",
        "createdby": "e2e",
        "usertoken": "NON_SECRET_E2E_TOKEN",
        "incompatible": "false",
    }
```

- [ ] **Step 2: Write `e2e/tests/stages.py`**

```python
"""One bounded wait per pipeline stage. Each returns what the next stage needs."""
from __future__ import annotations

import json
from dataclasses import dataclass

from clients import ActiveMQ, Postgres, Redis, S3, wait_until
from seed import Ids
from settings import Settings


@dataclass(frozen=True)
class ConversionResult:
    outputdocumentmasterid: int
    pdf_url: str


@dataclass(frozen=True)
class DedupeResult:
    documentid: int
    rank1hash: str
    compressionjobid: int


@dataclass(frozen=True)
class CompressionResult:
    status: str
    compressedfilepath: str | None


def _job_versions(pg: Postgres, table: str, idcol: str, jobid: int) -> list[tuple[int, str, str | None]]:
    return pg.all(
        f'SELECT version, status, message FROM "{table}" WHERE {idcol} = %s ORDER BY version',
        (jobid,),
    )


def _fail_if_error(versions, label: str) -> None:
    for version, status, message in versions:
        if status == "error":
            raise AssertionError(f"{label} failed at version {version}: {message or 'no message'}")


def wait_for_conversion(pg: Postgres, s3: S3, redis: Redis, settings: Settings, ids: Ids) -> ConversionResult:
    def done():
        versions = _job_versions(pg, "FileConversionJob", "fileconversionjobid", ids.jobid)
        _fail_if_error(versions, "conversion")
        return any(v == 3 and s == "completed" for v, s, _ in versions)

    wait_until(done, settings.stage_timeout,
               describe=lambda: f"FileConversionJob versions={_job_versions(pg, 'FileConversionJob', 'fileconversionjobid', ids.jobid)}")

    (outputid,) = pg.one(
        'SELECT outputdocumentmasterid FROM "FileConversionJob" WHERE fileconversionjobid = %s AND version = 3',
        (ids.jobid,),
    )
    (pdf_url, parentid) = pg.one(
        'SELECT filepath, processingparentid FROM "DocumentMaster" WHERE documentmasterid = %s', (outputid,)
    )
    assert parentid == ids.documentmasterid
    assert pdf_url.lower().endswith(".pdf")
    key = pdf_url.split(f"/{settings.s3_bucket}/", 1)[1]
    pdf = s3.get(key)
    assert pdf[:5] == b"%PDF-", "converted object is not a PDF"

    def dedupe_message():
        for _, fields in redis.entries(settings.dedupe_stream):
            if fields.get("documentmasterid") == str(ids.documentmasterid):
                return fields
        return None

    fields = wait_until(dedupe_message, settings.stage_timeout,
                        describe=lambda: f"no dedupe message for documentmasterid={ids.documentmasterid}")
    assert fields["s3filepath"] == pdf_url
    assert fields["outputdocumentmasterid"] == str(outputid)
    return ConversionResult(outputdocumentmasterid=outputid, pdf_url=pdf_url)


def wait_for_dedupe(pg: Postgres, redis: Redis, settings: Settings, ids: Ids, jobid: int | None = None) -> DedupeResult:
    dedupe_jobid = jobid if jobid is not None else ids.jobid

    def done():
        versions = _job_versions(pg, "DeduplicationJob", "deduplicationjobid", dedupe_jobid)
        _fail_if_error(versions, "dedupe")
        return any(v == 3 and s == "completed" for v, s, _ in versions)

    wait_until(done, settings.stage_timeout,
               describe=lambda: f"DeduplicationJob versions={_job_versions(pg, 'DeduplicationJob', 'deduplicationjobid', dedupe_jobid)}")

    row = wait_until(
        lambda: pg.one(
            '''SELECT d.documentid, h.rank1hash FROM "Documents" d
               JOIN "DocumentHashCodes" h ON h.documentid = d.documentid
               WHERE d.foiministryrequestid = %s ORDER BY d.documentid DESC LIMIT 1''',
            (ids.ministryrequestid,),
        ),
        settings.stage_timeout,
        describe=lambda: f"no Documents/DocumentHashCodes row for ministryrequestid={ids.ministryrequestid}",
    )
    documentid, rank1hash = row

    def compression_message():
        for _, fields in redis.entries(settings.compression_stream):
            if fields.get("documentmasterid") == str(ids.documentmasterid) or (
                "payload" in fields and json.loads(fields["payload"])["payload"]["documentmasterid"] == ids.documentmasterid
            ):
                return fields
        return None

    fields = wait_until(compression_message, settings.stage_timeout,
                        describe=lambda: f"no compression message for documentmasterid={ids.documentmasterid}")
    compressionjobid = int(fields["jobid"]) if "jobid" in fields else int(json.loads(fields["payload"])["payload"]["jobid"])

    def pagecount_message():
        return any(
            f.get("ministryrequestid") == str(ids.ministryrequestid)
            for _, f in redis.entries(settings.pagecount_stream)
        )

    wait_until(pagecount_message, settings.stage_timeout,
               describe=lambda: f"no pagecount message for ministryrequestid={ids.ministryrequestid}")
    return DedupeResult(documentid=documentid, rank1hash=rank1hash, compressionjobid=compressionjobid)


def wait_for_compression(pg: Postgres, s3: S3, settings: Settings, ids: Ids, compressionjobid: int) -> CompressionResult:
    def done():
        versions = _job_versions(pg, "CompressionJob", "compressionjobid", compressionjobid)
        _fail_if_error(versions, "compression")
        for v, s, _ in versions:
            if v == 3 and s in ("completed", "skipped"):
                return s
        return None

    status = wait_until(done, settings.stage_timeout,
                        describe=lambda: f"CompressionJob versions={_job_versions(pg, 'CompressionJob', 'compressionjobid', compressionjobid)}")
    (compressedfilepath,) = pg.one(
        'SELECT compressedfilepath FROM "DocumentMaster" WHERE documentmasterid = %s', (ids.documentmasterid,)
    )
    if status == "completed":
        assert compressedfilepath, "completed compression did not record compressedfilepath"
        key = compressedfilepath.split(f"/{settings.s3_bucket}/", 1)[1]
        assert s3.exists(key), f"compressed object missing: {key}"
    return CompressionResult(status=status, compressedfilepath=compressedfilepath)


def wait_for_ocr_dispatch(pg: Postgres, redis: Redis, activemq: ActiveMQ, settings: Settings, ids: Ids, compressionjobid: int) -> dict:
    def ocr_event():
        for _, fields in redis.entries(settings.ocr_stream):
            envelope = json.loads(fields["payload"])
            if envelope.get("event_type") == "document.ocr.requested" and envelope["payload"]["documentmasterid"] == ids.documentmasterid:
                return envelope
        return None

    wait_until(ocr_event, settings.stage_timeout,
               describe=lambda: f"no document.ocr.requested on {settings.ocr_stream} for documentmasterid={ids.documentmasterid}")

    def ocr_job_terminal():
        versions = _job_versions(pg, "OCRActiveMQJob", "ocractivemqjobid", compressionjobid)
        _fail_if_error(versions, "ocr dispatch")
        return any(v == 3 and s == "completed" for v, s, _ in versions)

    wait_until(ocr_job_terminal, settings.stage_timeout,
               describe=lambda: f"OCRActiveMQJob versions={_job_versions(pg, 'OCRActiveMQJob', 'ocractivemqjobid', compressionjobid)}")

    def queued_payload():
        message = activemq.consume_one()
        if message and message.get("documentmasterid") == ids.documentmasterid:
            return message
        return None

    payload = wait_until(queued_payload, settings.stage_timeout,
                         describe=lambda: f"no ActiveMQ message for documentmasterid={ids.documentmasterid}")
    assert payload["ministryrequestid"] == ids.ministryrequestid
    assert payload["bcgovcode"] == settings.bcgovcode
    assert payload.get("s3filepath") or payload.get("compresseds3filepath"), "OCR payload has no S3 path"
    return payload
```

- [ ] **Step 3: Write `e2e/tests/test_pdf_pipeline.py`**

```python
"""A dedupe-ready PDF: upload -> Dedupe -> Compression -> OCRServices -> ActiveMQ."""
from __future__ import annotations

import os

import seed
import stages

FILENAME = "sample.pdf"


def test_pdf_flows_through_dedupe_compression_and_ocr_dispatch(pg, redis_client, s3, activemq, settings, samples_dir):
    ids = seed.new_ids(prefix=1)
    sample = os.path.join(samples_dir, FILENAME)
    key = f"requests/{ids.requestnumber}/{FILENAME}"
    s3url = s3.url(key)
    filesize = os.path.getsize(sample)

    s3.put(key, sample, "application/pdf")
    seed.ensure_path_mapper(pg, settings.s3_bucket)
    seed.seed_pdf_upload(pg, ids, s3url, FILENAME, filesize)
    redis_client.xadd(settings.dedupe_stream, seed.upload_message(ids, s3url, FILENAME, filesize, ".pdf"))

    dedupe = stages.wait_for_dedupe(pg, redis_client, settings, ids)
    assert len(dedupe.rank1hash) == 40, "expected a sha1 hex digest"

    compression = stages.wait_for_compression(pg, s3, settings, ids, dedupe.compressionjobid)
    assert compression.status in ("completed", "skipped")

    payload = stages.wait_for_ocr_dispatch(pg, redis_client, activemq, settings, ids, dedupe.compressionjobid)
    expected_path = compression.compressedfilepath or s3url
    assert expected_path in (payload.get("compresseds3filepath"), payload.get("s3filepath"))
```

- [ ] **Step 4: Run and iterate until green**

Run: `./e2e/run.sh`
Expected: all readiness tests + `test_pdf_flows_through_dedupe_compression_and_ocr_dispatch` pass.

When a stage times out, the assertion message names the stage and the observed job versions; open `e2e/TestResults/compose.log` and search for that service. Fix only compose environment or test code. Known traps:
- Dedupe `document_processing_failed ... credentials`: `DocumentPathMapper` row missing or bucket name ≠ `citz-dev-e`.
- Dedupe SigV4 403 from SeaweedFS: `DEDUPE_S3_HOST` must equal the host in `s3filepath` (`seaweedfs:8333`).
- Dedupe logs `metadata_cleanup` error: expected (hard-coded `https://`); flow continues.
- Compression `errInvalidS3Object`: `s3filepath` must be `http://seaweedfs:8333/citz-dev-e/<key>`.
- OCRActiveMQJob stuck at version 1: check `ocr` logs for `activemq status 4xx` (auth/URL) or `connection refused` (Task 2 Step 4 Jetty binding).

- [ ] **Step 5: Commit**

```bash
git add e2e/tests/seed.py e2e/tests/stages.py e2e/tests/test_pdf_pipeline.py
git commit -m "test(e2e): assert pdf upload flows through dedupe, compression and ocr dispatch"
```

---

### Task 6: DOCX pipeline test (conversion first)

**Files:**
- Create: `e2e/tests/test_docx_pipeline.py`

**Interfaces:**
- Consumes: `seed.seed_docx_upload`, `stages.wait_for_conversion`, `stages.wait_for_dedupe(..., jobid=)`, `stages.wait_for_compression`, `stages.wait_for_ocr_dispatch`.

- [ ] **Step 1: Write `e2e/tests/test_docx_pipeline.py`**

```python
"""A conversion-required DOCX: upload -> File Conversion -> Dedupe -> Compression -> OCR dispatch."""
from __future__ import annotations

import os

import seed
import stages

FILENAME = "simple-test-doc.docx"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _dedupe_jobid_for(redis_client, settings, ids) -> int:
    for _, fields in redis_client.entries(settings.dedupe_stream):
        if fields.get("documentmasterid") == str(ids.documentmasterid):
            return int(fields["jobid"])
    raise AssertionError("dedupe message disappeared between stages")


def test_docx_flows_through_conversion_dedupe_compression_and_ocr_dispatch(pg, redis_client, s3, activemq, settings, samples_dir):
    ids = seed.new_ids(prefix=2)
    sample = os.path.join(samples_dir, FILENAME)
    key = f"requests/{ids.requestnumber}/{FILENAME}"
    s3url = s3.url(key)
    filesize = os.path.getsize(sample)

    s3.put(key, sample, DOCX_TYPE)
    seed.ensure_path_mapper(pg, settings.s3_bucket)
    seed.seed_docx_upload(pg, ids, s3url, FILENAME, filesize)
    redis_client.xadd(settings.conversion_stream, seed.upload_message(ids, s3url, FILENAME, filesize, ".docx"))

    conversion = stages.wait_for_conversion(pg, s3, redis_client, settings, ids)
    assert conversion.pdf_url == s3url[: -len(".docx")] + ".pdf"

    dedupe_jobid = _dedupe_jobid_for(redis_client, settings, ids)
    dedupe = stages.wait_for_dedupe(pg, redis_client, settings, ids, jobid=dedupe_jobid)
    assert len(dedupe.rank1hash) == 40

    compression = stages.wait_for_compression(pg, s3, settings, ids, dedupe.compressionjobid)
    assert compression.status in ("completed", "skipped")

    payload = stages.wait_for_ocr_dispatch(pg, redis_client, activemq, settings, ids, dedupe.compressionjobid)
    assert payload["documentmasterid"] == ids.documentmasterid
```

- [ ] **Step 2: Run and iterate until green**

Run: `./e2e/run.sh`
Expected: both pipeline tests pass.

Known trap: the converted PDF's `DocumentMaster` row (created by File Conversion) has the output id, while Dedupe writes `Documents.documentmasterid = outputdocumentmasterid`; `wait_for_dedupe` looks up by `foiministryrequestid`, so this is already handled. If Dedupe reports `credentials` failure only on this path, confirm File Conversion wrote the PDF under the same bucket (`citz-dev-e`).

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/test_docx_pipeline.py
git commit -m "test(e2e): assert docx upload is converted before dedupe, compression and ocr dispatch"
```

---

### Task 7: Duplicate-hash test

**Files:**
- Create: `e2e/tests/test_duplicate.py`

**Interfaces:**
- Consumes: `seed.*`, `stages.wait_for_dedupe`, `stages.wait_for_compression`, `stages.wait_for_ocr_dispatch`.

- [ ] **Step 1: Write `e2e/tests/test_duplicate.py`**

```python
"""Publishing the same PDF twice yields two Documents rows with one rank1hash."""
from __future__ import annotations

import os

import seed
import stages

FILENAME = "sample.pdf"


def _run_pdf(pg, redis_client, s3, activemq, settings, samples_dir, prefix: int):
    ids = seed.new_ids(prefix=prefix)
    sample = os.path.join(samples_dir, FILENAME)
    key = f"requests/{ids.requestnumber}/{FILENAME}"
    s3url = s3.url(key)
    filesize = os.path.getsize(sample)
    s3.put(key, sample, "application/pdf")
    seed.ensure_path_mapper(pg, settings.s3_bucket)
    seed.seed_pdf_upload(pg, ids, s3url, FILENAME, filesize)
    redis_client.xadd(settings.dedupe_stream, seed.upload_message(ids, s3url, FILENAME, filesize, ".pdf"))
    dedupe = stages.wait_for_dedupe(pg, redis_client, settings, ids)
    # Drain the rest of the pipeline so this document's ActiveMQ message does
    # not leak into a later test's consume_one().
    stages.wait_for_compression(pg, s3, settings, ids, dedupe.compressionjobid)
    stages.wait_for_ocr_dispatch(pg, redis_client, activemq, settings, ids, dedupe.compressionjobid)
    return dedupe


def test_same_pdf_twice_records_identical_hash(pg, redis_client, s3, activemq, settings, samples_dir):
    first = _run_pdf(pg, redis_client, s3, activemq, settings, samples_dir, prefix=3)
    second = _run_pdf(pg, redis_client, s3, activemq, settings, samples_dir, prefix=4)

    assert first.documentid != second.documentid
    assert first.rank1hash == second.rank1hash
```

- [ ] **Step 2: Run the whole suite**

Run: `./e2e/run.sh`
Expected: 9 passed (6 readiness + 3 pipeline), exit 0.

- [ ] **Step 3: Commit**

```bash
git add e2e/tests/test_duplicate.py
git commit -m "test(e2e): assert duplicate pdf uploads share a rank1 hash"
```

---

### Task 8: README, standard-mode switch check, and final verification

**Files:**
- Create: `e2e/README.md`

- [ ] **Step 1: Verify the standard (typed) compression mode also passes**

Run: `COMPRESSION_MESSAGING_MODE=standard ./e2e/run.sh`
Expected: 9 passed. (Dedupe publishes the typed envelope to `foi:compression`; `stages.wait_for_dedupe` already reads either `jobid` or `payload.payload.jobid`.) If `wait_for_dedupe` cannot find the message, the stream key is `foi:compression`, not `e2e-compression`: change `E2E_COMPRESSION_STREAM` in the `e2e-tests` service to `${E2E_COMPRESSION_STREAM:-e2e-compression}` and pass `E2E_COMPRESSION_STREAM=foi:compression` alongside `COMPRESSION_MESSAGING_MODE=standard`; document both variables in the README.

- [ ] **Step 2: Write `e2e/README.md`**

````markdown
# Pipeline end-to-end test

Runs the real service binaries in Docker Compose and pushes sample files through

```
S3 upload -> File Conversion (.NET) -> DedupeServices -> CompressionServices -> OCRServices -> ActiveMQ
```

`azureocrservices` and Azure Document Intelligence are not run; the test ends
when `OCRServices` has enqueued the OCR payload on the local ActiveMQ queue.

## Run

```bash
./e2e/run.sh                                   # legacy compression stream (default)
COMPRESSION_MESSAGING_MODE=standard ./e2e/run.sh  # typed foi:compression envelope
```

Requires Docker with Compose v2. The first run builds five images (api for
migrations, conversion, dedupe, compression, ocr) and takes several minutes.
Results land in `e2e/TestResults/`: `junit.xml` and `compose.log` (all
container output; printed to stderr on failure).

## What is asserted

| Stage | Evidence |
| --- | --- |
| Conversion (docx only) | `FileConversionJob` v3 `completed`; converted PDF in S3; message on `e2e-dedupe` |
| Dedupe | `DeduplicationJob` v3 `completed`; `Documents` + `DocumentHashCodes` rows; messages on the compression and `e2e-pagecount` streams |
| Compression | `CompressionJob` v3 `completed`/`skipped`; `DocumentMaster.compressedfilepath` object exists; `document.ocr.requested` on `foi:ocr` |
| OCR dispatch | `OCRActiveMQJob` v3 `completed`; payload consumed from ActiveMQ queue `foidococr` references the document |

Tests: `tests/test_pdf_pipeline.py`, `tests/test_docx_pipeline.py`,
`tests/test_duplicate.py`; `tests/test_readiness.py` fails fast when the
stack itself is broken.

## Adding a sample

1. Drop the file in `samples/`.
2. Copy `tests/test_pdf_pipeline.py` (dedupe-ready formats) or
   `tests/test_docx_pipeline.py` (conversion formats), change `FILENAME`,
   content type and the `seed.new_ids(prefix=...)` value to an unused prefix.
3. If the extension is new, add it to `fixtures/record-formats.json`.

## Layout

- `docker-compose.e2e.yml` – all services; credentials are test-only literals
- `run.sh` – up/down wrapper with log capture
- `fixtures/` – nginx record-formats stub, SeaweedFS identities
- `tests/` – pytest runner (`settings.py`, `clients.py`, `seed.py`, `stages.py`)

## Known local-only behaviour

DedupeServices hard-codes `https://` for its PDF metadata-cleanup upload; against
plain-HTTP SeaweedFS it logs `metadata_cleanup` and continues. Nothing asserts
on the `...ORIGINAL.pdf` copy.
````

- [ ] **Step 3: Final clean run**

Run: `./e2e/run.sh && ls e2e/TestResults`
Expected: `9 passed`, exit 0, `compose.log junit.xml`.

- [ ] **Step 4: Confirm nothing outside `e2e/` and `docs/` changed**

Run: `git status --porcelain | grep -v '^??' | grep -v '^ M \(api/README.md\|computingservices/.*Dockerfile.local\|docker-compose.yml\|sample.env\|web/\)'`
Expected: no output (only the pre-existing unrelated modifications remain).

- [ ] **Step 5: Commit**

```bash
git add e2e/README.md e2e/docker-compose.e2e.yml
git commit -m "docs(e2e): document the pipeline end-to-end harness"
```
