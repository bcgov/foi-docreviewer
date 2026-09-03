# Redis-Only Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip the FastAPI + PostgreSQL layers out of the template, leaving a Redis Streams worker that consumes an event, computes a result, publishes a follow-on event, and carries one unbroken distributed trace across every hop.

**Architecture:** Two processes over one image. `main.py` is a worker running `RedisConsumer` and a stdlib-asyncio health server on one event loop; `cli.py` is a one-shot publisher. Redis is the event stream, the dead-letter stream, and the handler's state store. Trace context travels in a `traceparent` field on the event envelope, injected from ambient context by the producer and made current by the consumer, so a handler's publish automatically continues the trace.

**Tech Stack:** Python 3.14, `redis.asyncio`, Pydantic v2 + pydantic-settings, structlog, OpenTelemetry (API/SDK/OTLP HTTP), pytest + pytest-asyncio + testcontainers, Poetry, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-27-redis-only-template-design.md`

## Global Constraints

- Python `^3.14`. Poetry, `package-mode = false`.
- Line length 88 (Black default). Ruff selects `E, F, W, B, I`, ignores `E501, B008`.
- Import order: standard library, third-party, local.
- `asyncio_mode = "auto"` in pytest config — async tests need no decorator.
- Tests that need Docker are marked `pytest.mark.integration` via a module-level `pytestmark`; `make test` runs `-m "not integration"`.
- Money is **integer minor units** everywhere: `1000` means `10.00`. Fields carry a `_cents` suffix. Never `float`, never `Decimal`. Formatting happens only at output edges via `format_cents()`.
- Every handler must be idempotent, and must not emit downstream events on a redelivery.
- The consumer's per-message span MUST be the **active** context during dispatch (`start_as_current_span`), never a detached span.
- No `create_all`, no ORM, no migrations — those layers are being deleted, not replaced.
- Run `make lint` before each commit; run `make fmt` if it complains about formatting.

---

### Task 1: Strip the API, database, and their dependencies

Deletion-first task. Nothing here is TDD in the write-a-failing-test sense — the "test" is that the surviving suite still passes and the package imports with no `DATABASE_URL` in the environment.

**Files:**
- Delete: `api/` (whole tree), `core/` (whole tree), `db/` (whole tree), `alembic.ini`, `docker-entrypoint.sh`, `config/request_logger.py`
- Delete: `tests/integration/test_migrations.py`, `tests/integration/test_order_repository.py`, `tests/integration/test_order_routes.py`, `tests/unit/test_order_service.py`
- Modify: `config/settings.py`, `config/tracing.py`, `pyproject.toml`, `tests/conftest.py`
- Test: `tests/unit/test_settings.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `Settings` with no `DATABASE_URL`, plus `HEALTH_PORT: int = 8000` and `STATE_TTL_SECONDS: int = 3600`; `init_tracing() -> None` with no `app` parameter; a `conftest.py` exposing only `redis_url`, `app_settings`, and `redis_client` fixtures.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_settings.py`:

```python
import os

from config.settings import Settings


def test_settings_construct_with_no_environment_at_all(monkeypatch):
    """
    DATABASE_URL was the only required field. With the database layer gone the
    template must be runnable with zero configuration — a new user should be
    able to `python main.py` against a default local Redis.
    """
    for key in list(os.environ):
        if key.startswith(("DATABASE", "REDIS", "STREAM", "CONSUMER", "HEALTH", "STATE")):
            monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.REDIS_STREAM_URL == "redis://localhost:6379/1"
    assert settings.HEALTH_PORT == 8000
    assert settings.STATE_TTL_SECONDS == 3600
    assert not hasattr(settings, "DATABASE_URL")
    assert not hasattr(settings, "SERVICE_PORT")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_settings.py -v`
Expected: FAIL — `SERVICE_PORT` and `DATABASE_URL` still exist, so the two `hasattr` assertions fail.

- [ ] **Step 3: Delete the API, core, and database layers**

```bash
git rm -r api core db
git rm alembic.ini docker-entrypoint.sh config/request_logger.py
git rm tests/integration/test_migrations.py \
       tests/integration/test_order_repository.py \
       tests/integration/test_order_routes.py \
       tests/unit/test_order_service.py
```

- [ ] **Step 4: Update `config/settings.py`**

Delete the `DATABASE_URL` field and the `# Database Configuration` comment block. Delete `SERVICE_PORT`. Add to the environment-metadata block and a new state block:

```python
    ENVIRONMENT: str = "development"  # development | staging | production
    SERVICE_NAME: str = "python-microservice-template"
    SERVICE_VERSION: str = "0.1.0"

    # SERVICE_NAME / SERVICE_VERSION / ENVIRONMENT have exactly one consumer
    # now: the OpenTelemetry Resource in config/tracing.py, which stamps them
    # on every exported span. The /info endpoint that used to serve them is
    # gone — the collector has the same three values.

    # -------------------------
    # Health probe server
    # -------------------------
    HEALTH_PORT: int = 8000

    # -------------------------
    # Handler state store
    # -------------------------
    STATE_TTL_SECONDS: int = 3600
```

- [ ] **Step 5: Update `config/tracing.py`**

Remove `from fastapi import FastAPI`, `from typing import Optional`, and `from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor`. Change the signature and drop the instrumentation block at the end:

```python
def init_tracing() -> None:
    """
    Initialize OpenTelemetry tracing. Safe to call multiple times (idempotent).

    There is no ASGI app to auto-instrument any more. Spans are created
    explicitly by the producer, the consumer and the CLI — see
    messaging/producer/redis_producer.py and messaging/consumer/redis_consumer.py.
    """
```

Delete these trailing lines:

```python
    # Instrument FastAPI app if provided
    if app is not None:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
```

Keep `_tracer_initialized = True` as the last statement.

- [ ] **Step 6: Update `pyproject.toml`**

Change the description, and delete the web-framework, database, and migration dependency blocks:

```toml
description = "An async Redis Streams producer/consumer microservice template with tracing, retries and dead-lettering."
```

Delete these lines from `[tool.poetry.dependencies]`:

```toml
# --- Web Framework ---
fastapi = "^ 0.122.0"
uvicorn = { extras = ["standard"], version = "^0.38.0" }

# --- Database / ORM ---
sqlalchemy = "^2.0.44"
asyncpg = "^0.31.0"

# --- Database Migrations ---
alembic = "^1.16.0"
```

Also delete `opentelemetry-instrumentation-fastapi = "^0.59b0"`.

In `[tool.poetry.group.dev.dependencies]`, narrow testcontainers and drop the HTTP client:

```toml
testcontainers = { extras = ["redis"], version = "^4.9.0" }
```

Delete `httpx = "^0.28.0"`.

Update the marker description and coverage omit list:

```toml
markers = [
    "integration: requires Docker (Redis testcontainer)",
]
```

```toml
omit = [
    "tests/*",
    ".venv/*",
]
```

- [ ] **Step 7: Rewrite `tests/conftest.py`**

Replace the whole file. Everything Postgres-related goes, including all three engine-globals fixtures — they existed only because `db.postgres.session` cached an engine in module globals.

```python
# tests/conftest.py

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def redis_url() -> str:
    """Start a throwaway Redis and yield its URL."""
    with RedisContainer("redis:7") as rc:
        host = rc.get_container_host_ip()
        port = rc.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def app_settings(redis_url: str):
    """
    Point the application's cached settings at the container.

    get_settings() is lru_cached, so the env must be set and the cache cleared
    before anything imports a Redis client.
    """
    from config.settings import get_settings

    os.environ["REDIS_STREAM_URL"] = redis_url
    os.environ["STREAM_NAME"] = "test.order.events"
    os.environ["CONSUMER_GROUP"] = "test_group"
    os.environ["CONSUMER_RETRY_BACKOFF_MS"] = "10"
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def redis_client(app_settings) -> AsyncGenerator:
    """
    Redis client with the streams and any demo state keys cleared before and
    after. Handlers write order:* hashes, so leaving them behind would make a
    later test's HSETNX return 0 and silently change its meaning.
    """
    from redis.asyncio import Redis

    client = Redis.from_url(app_settings.REDIS_STREAM_URL, decode_responses=True)

    async def _flush():
        await client.delete(app_settings.STREAM_NAME, app_settings.dlq_stream)
        keys = [k async for k in client.scan_iter(match="order:*")]
        if keys:
            await client.delete(*keys)

    await _flush()
    yield client
    await _flush()
    await client.aclose()
```

- [ ] **Step 8: Run the test suite**

Run: `poetry lock && poetry install && poetry run pytest tests/unit -v`
Expected: `tests/unit/test_settings.py` PASSES. `test_main.py` FAILS on `from main import app` — that is expected and is fixed in Task 7. `test_dispatcher.py`, `test_envelope.py`, `test_redis_consumer.py` pass.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor: remove API, database and migration layers"
```

---

### Task 2: Money helper and the two event payloads

**Files:**
- Create: `money.py`, `messaging/models/events/order_confirmed.py`
- Modify: `messaging/models/events/order_created.py`, `messaging/models/envelope.py`, `messaging/models/__init__.py`
- Test: `tests/unit/test_money.py` (create), `tests/unit/test_envelope.py` (modify)

**Interfaces:**
- Consumes: `Settings` from Task 1.
- Produces:
  - `format_cents(cents: int) -> str`
  - `OrderCreatedEvent(order_ref: str, item: str, quantity: int, unit_price_cents: int)`
  - `OrderConfirmedEvent(order_ref: str, total_cents: int, confirmed_at: datetime)`
  - `EventPayload = OrderCreatedEvent | OrderConfirmedEvent`
  - `EventEnvelope` with `event_type: Literal["OrderCreated", "OrderConfirmed"]` and `traceparent: str | None = None`
  - `EventEnvelope.create(event_type, payload, correlation_id, source)` — unchanged signature

- [ ] **Step 1: Write the failing money test**

Create `tests/unit/test_money.py`:

```python
import pytest

from money import format_cents


@pytest.mark.parametrize(
    ("cents", "expected"),
    [
        (0, "0.00"),
        (5, "0.05"),
        (50, "0.50"),
        (450, "4.50"),
        (1000, "10.00"),
        (1350, "13.50"),
        (123456, "1234.56"),
        (-1350, "-13.50"),
        (-5, "-0.05"),
    ],
)
def test_format_cents(cents: int, expected: str):
    assert format_cents(cents) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_money.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'money'`

- [ ] **Step 3: Write `money.py`**

```python
# money.py
"""
Money handling for the template.

Amounts are integer minor units everywhere: 1000 means 10.00. Integers are
exact, they serialise to JSON as themselves, and they cross a stream into a
consumer written in any other language without a precision conversation.
Floats cannot represent money exactly and are never used here.

This module is the only place a cents value becomes a human-readable string.
Payload models carry ints; formatting happens at output edges — log lines and
CLI output — so the wire format never depends on presentation.
"""


def format_cents(cents: int) -> str:
    """Render integer minor units for humans: 1350 -> '13.50'."""
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fraction:02d}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/unit/test_money.py -v`
Expected: PASS (9 parametrized cases)

- [ ] **Step 5: Write the failing envelope tests**

Append to `tests/unit/test_envelope.py`:

```python
from datetime import UTC, datetime

from messaging.models import EventEnvelope, OrderConfirmedEvent, OrderCreatedEvent


def make_created():
    return OrderCreatedEvent(
        order_ref="r1", item="widget", quantity=3, unit_price_cents=450
    )


def test_order_confirmed_envelope_round_trips_to_the_right_payload_type():
    """
    EventPayload is a union now. Pydantic must resolve a serialised
    OrderConfirmed back to OrderConfirmedEvent, not coerce it into the first
    member of the union.
    """
    env = EventEnvelope.create(
        event_type="OrderConfirmed",
        payload=OrderConfirmedEvent(
            order_ref="r1", total_cents=1350, confirmed_at=datetime.now(UTC)
        ),
        correlation_id="corr-1",
        source="consumer",
    )

    parsed = EventEnvelope.model_validate_json(env.model_dump_json())

    assert isinstance(parsed.payload, OrderConfirmedEvent)
    assert parsed.payload.total_cents == 1350


def test_totals_survive_the_json_round_trip_as_exact_ints():
    env = EventEnvelope.create(
        event_type="OrderConfirmed",
        payload=OrderConfirmedEvent(
            order_ref="r1", total_cents=100000000000, confirmed_at=datetime.now(UTC)
        ),
        correlation_id="corr-1",
        source="consumer",
    )

    parsed = EventEnvelope.model_validate_json(env.model_dump_json())

    assert parsed.payload.total_cents == 100000000000
    assert isinstance(parsed.payload.total_cents, int)


def test_fractional_unit_price_is_rejected_not_silently_truncated():
    """
    A publisher sending 4.5 means 4.5 cents, which is not representable. It
    must fail validation at the boundary rather than becoming 4 somewhere
    downstream.
    """
    with pytest.raises(ValidationError):
        OrderCreatedEvent(
            order_ref="r1", item="widget", quantity=1, unit_price_cents=4.5
        )


def test_traceparent_is_optional_and_defaults_to_none():
    env = EventEnvelope.create(
        event_type="OrderCreated",
        payload=make_created(),
        correlation_id="corr-1",
        source="cli",
    )

    assert env.traceparent is None
    assert EventEnvelope.model_validate_json(env.model_dump_json()).traceparent is None


def test_traceparent_survives_the_round_trip():
    env = EventEnvelope.create(
        event_type="OrderCreated",
        payload=make_created(),
        correlation_id="corr-1",
        source="cli",
    )
    env = env.model_copy(
        update={"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
    )

    parsed = EventEnvelope.model_validate_json(env.model_dump_json())

    assert parsed.traceparent == env.traceparent
```

Make sure the file's imports include `import pytest` and `from pydantic import ValidationError`, and update any existing `OrderCreatedEvent(...)` construction in the file to pass `unit_price_cents=450`.

- [ ] **Step 6: Run tests to verify they fail**

Run: `poetry run pytest tests/unit/test_envelope.py -v`
Expected: FAIL — `ImportError: cannot import name 'OrderConfirmedEvent'`

- [ ] **Step 7: Add `unit_price_cents` to the OrderCreated payload**

Rewrite `messaging/models/events/order_created.py`:

```python
from pydantic import BaseModel, Field


class OrderCreatedEvent(BaseModel):
    """
    Payload for the OrderCreated event — the *inputs* to the processing step.

    unit_price_cents is integer minor units: 450 means 4.50. See money.py.
    """

    order_ref: str = Field(min_length=1, max_length=255)
    item: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0)
    unit_price_cents: int = Field(ge=0)

    model_config = {"extra": "forbid"}
```

- [ ] **Step 8: Create the OrderConfirmed payload**

Create `messaging/models/events/order_confirmed.py`:

```python
from datetime import datetime

from pydantic import BaseModel, Field


class OrderConfirmedEvent(BaseModel):
    """
    Payload for the OrderConfirmed event — the *output* of the processing step.

    total_cents is integer minor units and is computed by the OrderCreated
    handler; it is a value that did not exist on the inbound event.
    """

    order_ref: str = Field(min_length=1, max_length=255)
    total_cents: int = Field(ge=0)
    confirmed_at: datetime

    model_config = {"extra": "forbid"}
```

- [ ] **Step 9: Widen the envelope**

In `messaging/models/envelope.py`, change the import, the union, the `Literal`, and add the `traceparent` field:

```python
from messaging.models.events.order_confirmed import OrderConfirmedEvent
from messaging.models.events.order_created import OrderCreatedEvent

# Add your payload types to this union as the service grows.
EventPayload = OrderCreatedEvent | OrderConfirmedEvent
```

```python
    event_type: Literal["OrderCreated", "OrderConfirmed"]
```

Add below `source: str`, before `payload`:

```python
    # W3C trace context, injected by the producer from whatever span is
    # current and extracted by the consumer to parent its message span.
    # Optional: an envelope published outside a trace simply starts one.
    traceparent: str | None = None
```

- [ ] **Step 10: Export the new payload**

Rewrite `messaging/models/__init__.py`:

```python
from .envelope import SCHEMA_VERSION, EventEnvelope, EventPayload
from .events.order_confirmed import OrderConfirmedEvent
from .events.order_created import OrderCreatedEvent

__all__ = [
    "SCHEMA_VERSION",
    "EventEnvelope",
    "EventPayload",
    "OrderConfirmedEvent",
    "OrderCreatedEvent",
]
```

- [ ] **Step 11: Fix the surviving tests that build an OrderCreated payload**

Adding a required field breaks every existing construction of it. Three files
outside this task's test file build one:

In `tests/integration/test_producer.py:17`:

```python
        payload=OrderCreatedEvent(
            order_ref="r1", item="widget", quantity=1, unit_price_cents=450
        ),
```

In `tests/integration/test_consumer.py:17`:

```python
        payload=OrderCreatedEvent(
            order_ref=order_ref, item="widget", quantity=1, unit_price_cents=450
        ),
```

`tests/integration/test_consumer.py` also still requests the deleted
`migrated_db` fixture. In `test_valid_message_is_handled_and_acked`, change the
signature from:

```python
async def test_valid_message_is_handled_and_acked(
    app_settings, migrated_db, redis_client, monkeypatch
):
```

to:

```python
async def test_valid_message_is_handled_and_acked(
    app_settings, redis_client, monkeypatch
):
```

Check the other two tests in that file for `migrated_db` and remove it there
too — grep is faster than reading:

```bash
grep -rn "migrated_db\|db_session" tests/
```

Expected after the edits: no hits.

`tests/unit/test_dispatcher.py` also builds one; it is updated in Task 5.

- [ ] **Step 12: Run tests to verify they pass**

Run: `poetry run pytest tests/unit/test_envelope.py tests/unit/test_money.py -v`
Expected: PASS

Then confirm nothing else broke on the payload change:

Run: `poetry run pytest tests/integration/test_producer.py tests/integration/test_consumer.py -v`
Expected: PASS — these exercise the producer and consumer, which this task did
not change; they are here to catch the payload edit, not to test new code.

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "feat: add OrderConfirmed payload, cents money handling and traceparent"
```

---

### Task 3: Handler state store

A tiny module so handlers get a Redis client without borrowing the consumer's.

**Files:**
- Create: `messaging/state.py`
- Test: `tests/unit/test_state.py` (create)

**Interfaces:**
- Consumes: `get_settings()`.
- Produces: `get_state_client() -> Redis`, `close_state_client() -> None`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_state.py`:

```python
from messaging import state


def test_get_state_client_is_process_wide_and_lazy():
    """
    Lazily constructed: importing the module must not open a socket, or every
    importer needs a live Redis. Same instance thereafter, so handlers share
    one connection pool rather than one per message.
    """
    assert state._client is None

    first = state.get_state_client()
    second = state.get_state_client()

    assert first is second
    assert state._client is first


async def test_close_state_client_resets_the_global():
    state.get_state_client()
    await state.close_state_client()
    assert state._client is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/test_state.py -v`
Expected: FAIL with `ImportError: cannot import name 'state'`

- [ ] **Step 3: Write `messaging/state.py`**

```python
# messaging/state.py
"""
The handler-side Redis client.

Deliberately separate from the consumer's client. A handler has no ambient
request context — there is no Depends(get_db) equivalent — so it acquires its
own resources, and it must not reach into the consumer's connection to do it.
Keeping them apart means a handler cannot accidentally issue a blocking
command on the connection the read loop depends on.
"""

from redis.asyncio import Redis

from config.logging import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

_client: Redis | None = None


def get_state_client() -> Redis:
    """
    Process-wide state client. Lazily constructed so importing this module
    does not open a socket.
    """
    global _client
    if _client is None:
        _client = Redis.from_url(
            get_settings().REDIS_STREAM_URL, decode_responses=True
        )
    return _client


async def close_state_client() -> None:
    """Dispose of the process-wide state client. Called on worker shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.debug("Redis state client closed")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/unit/test_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add handler-side Redis state client"
```

---

### Task 4: Rewrite the OrderCreated handler — consume, compute, publish

The centre of the template. Three properties must hold: state is written idempotently, the total is computed, and a redelivery publishes nothing.

**Files:**
- Modify: `messaging/consumer/handlers/order_created.py`
- Test: `tests/integration/test_order_created_handler.py` (rewrite)

**Interfaces:**
- Consumes: `get_state_client()` (Task 3), `OrderCreatedEvent` / `OrderConfirmedEvent` / `EventEnvelope` (Task 2), `format_cents()` (Task 2), `get_producer()` from `messaging/producer/redis_producer.py`.
- Produces: `handle(payload: OrderCreatedEvent, *, correlation_id: str) -> None`.

- [ ] **Step 1: Write the failing tests**

Replace `tests/integration/test_order_created_handler.py` entirely:

```python
import pytest

from messaging.consumer.handlers.order_created import handle
from messaging.models import EventEnvelope, OrderConfirmedEvent, OrderCreatedEvent
from messaging.producer.redis_producer import close_producer
from messaging.state import close_state_client

pytestmark = pytest.mark.integration


def make_payload(ref="r1", quantity=3, unit_price_cents=450):
    return OrderCreatedEvent(
        order_ref=ref,
        item="widget",
        quantity=quantity,
        unit_price_cents=unit_price_cents,
    )


@pytest.fixture(autouse=True)
async def _close_clients(app_settings):
    """
    The handler's module-level clients bind to the event loop that created
    them, and pytest-asyncio gives each test its own loop. Close them after
    every test or the second test to run fails with "Event loop is closed".
    """
    yield
    await close_state_client()
    await close_producer()


async def test_first_delivery_confirms_computes_and_publishes(
    app_settings, redis_client
):
    await handle(make_payload(), correlation_id="corr-1")

    stored = await redis_client.hgetall("order:r1")
    assert stored["status"] == "confirmed"
    assert stored["item"] == "widget"
    assert stored["quantity"] == "3"
    assert stored["total_cents"] == "1350"
    assert stored["confirmed_at"]

    ttl = await redis_client.ttl("order:r1")
    assert 0 < ttl <= app_settings.STATE_TTL_SECONDS

    entries = await redis_client.xrange(app_settings.STREAM_NAME)
    assert len(entries) == 1
    envelope = EventEnvelope.model_validate_json(entries[0][1]["event"])
    assert envelope.event_type == "OrderConfirmed"
    assert envelope.source == "consumer"
    assert envelope.correlation_id == "corr-1"
    assert isinstance(envelope.payload, OrderConfirmedEvent)
    assert envelope.payload.total_cents == 1350


async def test_redelivery_is_a_no_op_and_publishes_nothing(app_settings, redis_client):
    """
    The whole point. Redis Streams delivers at least once, so this handler runs
    again on redelivery. Local state staying correct is not enough — a
    duplicate inbound event must not become a duplicate outbound event, or one
    redelivery amplifies through every downstream consumer.
    """
    await handle(make_payload(), correlation_id="corr-1")
    await handle(make_payload(), correlation_id="corr-1")

    entries = await redis_client.xrange(app_settings.STREAM_NAME)
    assert len(entries) == 1, "redelivery must not publish a second OrderConfirmed"


async def test_redelivery_does_not_overwrite_the_stored_total(
    app_settings, redis_client
):
    await handle(make_payload(quantity=3, unit_price_cents=450), correlation_id="c")
    await handle(make_payload(quantity=9, unit_price_cents=999), correlation_id="c")

    stored = await redis_client.hgetall("order:r1")
    assert stored["total_cents"] == "1350"


async def test_total_is_exact_for_large_amounts(app_settings, redis_client):
    await handle(
        make_payload(quantity=3, unit_price_cents=333_333_333), correlation_id="c"
    )

    stored = await redis_client.hgetall("order:r1")
    assert stored["total_cents"] == "999999999"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/integration/test_order_created_handler.py -v`
Expected: FAIL — the current handler imports `db.postgres.session`, which no longer exists, so collection errors with `ModuleNotFoundError: No module named 'db'`.

- [ ] **Step 3: Rewrite the handler**

Replace `messaging/consumer/handlers/order_created.py` entirely:

```python
from datetime import UTC, datetime

from config.logging import get_logger
from config.settings import get_settings
from messaging.models import EventEnvelope, OrderConfirmedEvent, OrderCreatedEvent
from messaging.producer.redis_producer import get_producer
from messaging.state import get_state_client
from money import format_cents

logger = get_logger(__name__)


async def handle(payload: OrderCreatedEvent, *, correlation_id: str) -> None:
    """
    Consume, compute, publish — the shape every handler in this template takes.

    IDEMPOTENCY: Redis Streams delivers at least once, so this runs again on
    any redelivery. HSETNX is the guard: it writes only if the field is absent,
    so exactly one delivery per order_ref takes the work path. Note where the
    early return sits — BEFORE the publish. Correct local state is only half of
    idempotency; the other half is not amplifying a redelivery into a duplicate
    downstream event.

    NON-ATOMICITY, on purpose: HSETNX and EXPIRE are two round trips, so a
    crash between them leaves a key with no TTL. A Lua script or a SET NX with
    an embedded TTL would be atomic. For a demo state store the simpler code is
    worth more than the guarantee — but do not copy this shape into a place
    where the TTL is load-bearing.

    RESOURCES: the handler takes its own Redis client (messaging/state.py)
    rather than the consumer's. There is no request scope here to inherit one
    from.

    FAILURE WINDOW, documented rather than solved: if HSETNX succeeds and the
    publish below fails, this raises and the message is retried — but the retry
    finds HSETNX returning 0 and takes the early return, so OrderConfirmed is
    never published. The state is right and the downstream event is lost. That
    is the write-then-publish problem every service with a database and a
    broker has; the real answer is a transactional outbox, which is more
    machinery than a template should carry. Know that it is here before you
    copy this into something that matters.
    """
    log = logger.bind(order_ref=payload.order_ref, correlation_id=correlation_id)

    redis = get_state_client()
    key = f"order:{payload.order_ref}"

    if not await redis.hsetnx(key, "status", "confirmed"):
        log.info("Order already processed; nothing to do")
        return

    # The processing step. Integer arithmetic on minor units, exact by
    # construction. Replace this with whatever your service actually does.
    total_cents = payload.quantity * payload.unit_price_cents
    confirmed_at = datetime.now(UTC)

    await redis.hset(
        key,
        mapping={
            "item": payload.item,
            "quantity": payload.quantity,
            "total_cents": total_cents,
            "confirmed_at": confirmed_at.isoformat(),
        },
    )
    await redis.expire(key, get_settings().STATE_TTL_SECONDS)

    # Publishing from inside a handler is what makes this service a node in a
    # pipeline rather than a leaf. The producer reads ambient trace context, so
    # this event is automatically a child of the span for the message being
    # handled — see messaging/consumer/redis_consumer.py.
    await get_producer().publish(
        EventEnvelope.create(
            event_type="OrderConfirmed",
            payload=OrderConfirmedEvent(
                order_ref=payload.order_ref,
                total_cents=total_cents,
                confirmed_at=confirmed_at,
            ),
            correlation_id=correlation_id,
            source="consumer",
        )
    )

    log.info("Order confirmed", total=format_cents(total_cents))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/integration/test_order_created_handler.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: OrderCreated handler computes a total and publishes OrderConfirmed"
```

---

### Task 5: OrderConfirmed handler and dispatcher registration

**Files:**
- Create: `messaging/consumer/handlers/order_confirmed.py`
- Modify: `messaging/consumer/dispatcher.py`
- Test: `tests/unit/test_order_confirmed_handler.py` (create), `tests/unit/test_dispatcher.py` (modify)

**Interfaces:**
- Consumes: `OrderConfirmedEvent` (Task 2), `format_cents()` (Task 2).
- Produces: `handle(payload: OrderConfirmedEvent, *, correlation_id: str) -> None`; `HANDLERS` gains an `"OrderConfirmed"` row.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_order_confirmed_handler.py`:

```python
from datetime import UTC, datetime

from messaging.consumer import dispatcher
from messaging.consumer.handlers.order_confirmed import handle
from messaging.models import EventEnvelope, OrderConfirmedEvent


def make_payload():
    return OrderConfirmedEvent(
        order_ref="r1", total_cents=1350, confirmed_at=datetime.now(UTC)
    )


async def test_handle_is_side_effect_free_and_does_not_raise():
    """
    The terminal hop. It must not publish anything — a handler that republished
    onto the same stream would loop the worker forever.
    """
    await handle(make_payload(), correlation_id="corr-1")


async def test_order_confirmed_is_registered_in_the_dispatcher():
    assert "OrderConfirmed" in dispatcher.HANDLERS


async def test_dispatch_routes_an_order_confirmed_envelope_to_its_handler(monkeypatch):
    seen = {}

    async def fake_handle(payload, *, correlation_id):
        seen["total_cents"] = payload.total_cents

    monkeypatch.setitem(dispatcher.HANDLERS, "OrderConfirmed", fake_handle)
    await dispatcher.dispatch_event(
        EventEnvelope.create(
            event_type="OrderConfirmed",
            payload=make_payload(),
            correlation_id="corr-1",
            source="consumer",
        )
    )

    assert seen == {"total_cents": 1350}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/unit/test_order_confirmed_handler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'messaging.consumer.handlers.order_confirmed'`

- [ ] **Step 3: Write the handler**

Create `messaging/consumer/handlers/order_confirmed.py`:

```python
from config.logging import get_logger
from messaging.models import OrderConfirmedEvent
from money import format_cents

logger = get_logger(__name__)


async def handle(payload: OrderConfirmedEvent, *, correlation_id: str) -> None:
    """
    The terminal hop of the sample pipeline.

    Deliberately side-effect-free: it exists so the consumer-as-producer step
    in the OrderCreated handler has a real consumer, which is what makes the
    distributed trace span two process hops instead of one.

    It has no idempotency guard because it has no state to guard — see
    handlers/order_created.py for the HSETNX pattern to copy when your handler
    does write something.

    DO NOT publish OrderCreated from here. Both event types share one stream,
    so a handler that republishes upstream gives you an infinite loop that
    looks exactly like a busy worker.
    """
    logger.bind(
        order_ref=payload.order_ref, correlation_id=correlation_id
    ).info(
        "Order confirmation received",
        total=format_cents(payload.total_cents),
        confirmed_at=payload.confirmed_at.isoformat(),
    )
```

- [ ] **Step 4: Register it**

In `messaging/consumer/dispatcher.py`, add the import and the registry row:

```python
from messaging.consumer.handlers.order_confirmed import handle as handle_order_confirmed
from messaging.consumer.handlers.order_created import handle as handle_order_created
```

```python
# Event routing table. Register new event types here.
HANDLERS: dict[str, Handler] = {
    "OrderCreated": handle_order_created,
    "OrderConfirmed": handle_order_confirmed,
}
```

- [ ] **Step 5: Update the existing dispatcher test**

In `tests/unit/test_dispatcher.py`, update `make_envelope` so the payload matches the new `OrderCreatedEvent` shape:

```python
def make_envelope(event_type="OrderCreated"):
    return EventEnvelope.create(
        event_type=event_type,
        payload=OrderCreatedEvent(
            order_ref="r1", item="widget", quantity=1, unit_price_cents=450
        ),
        correlation_id="corr-1",
        source="test",
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `poetry run pytest tests/unit -v`
Expected: PASS, except `test_main.py` which still fails on `from main import app` (fixed in Task 7).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add OrderConfirmed handler and register it"
```

---

### Task 6: Health probe server

**Files:**
- Create: `health/__init__.py`, `health/server.py`
- Test: `tests/integration/test_health.py` (rewrite)

**Interfaces:**
- Consumes: `get_settings()`.
- Produces: `start_health_server(port: int | None = None) -> asyncio.Server`, `PROBE_TIMEOUT_SECONDS: float`.

- [ ] **Step 1: Write the failing tests**

Replace `tests/integration/test_health.py` entirely:

```python
import asyncio
import json

import pytest

from health.server import start_health_server

pytestmark = pytest.mark.integration


async def request(port: int, path: str = "/health") -> tuple[int, dict]:
    """Minimal HTTP client — the server is minimal, the client can be too."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode())
    await writer.drain()
    raw = await reader.read()
    writer.close()
    await writer.wait_closed()

    head, _, body = raw.partition(b"\r\n\r\n")
    status = int(head.split(b"\r\n")[0].split()[1])
    return status, json.loads(body)


async def serve_on_ephemeral_port():
    server = await start_health_server(port=0)
    return server, server.sockets[0].getsockname()[1]


async def test_health_returns_200_when_redis_is_reachable(app_settings):
    server, port = await serve_on_ephemeral_port()
    try:
        status, body = await request(port)
    finally:
        server.close()
        await server.wait_closed()

    assert status == 200
    assert body == {"status": "ok", "redis": "ok"}


async def test_health_returns_503_when_redis_is_unreachable(app_settings, monkeypatch):
    """
    A health endpoint that always returns 200 teaches the wrong reflex: it
    tells your orchestrator the worker is fine while it cannot reach the
    stream it exists to consume.
    """
    from config.settings import get_settings

    monkeypatch.setenv("REDIS_STREAM_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()

    server, port = await serve_on_ephemeral_port()
    try:
        status, body = await request(port)
    finally:
        server.close()
        await server.wait_closed()
        get_settings.cache_clear()

    assert status == 503
    assert body == {"status": "degraded", "redis": "down"}


async def test_unknown_path_returns_404(app_settings):
    server, port = await serve_on_ephemeral_port()
    try:
        status, _ = await request(port, "/info")
    finally:
        server.close()
        await server.wait_closed()

    assert status == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/integration/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'health'`

- [ ] **Step 3: Create the package marker**

Create an empty `health/__init__.py`:

```python
# health/__init__.py
```

- [ ] **Step 4: Write `health/server.py`**

```python
# health/server.py
"""
A probe endpoint, not a web framework.

The worker has no HTTP surface, but an orchestrator still needs to ask whether
it is alive and whether it can reach Redis. That is roughly forty lines of
asyncio, so it does not justify a dependency on an ASGI server. Everything
here is deliberately unambitious: one route, no keep-alive, no routing table,
no request body parsing.
"""

import asyncio
import json

from redis.asyncio import Redis

from config.logging import get_logger
from config.settings import get_settings

logger = get_logger(__name__)

PROBE_TIMEOUT_SECONDS = 2.0
REQUEST_LINE_TIMEOUT_SECONDS = 5.0


async def _redis_is_reachable() -> bool:
    client = Redis.from_url(get_settings().REDIS_STREAM_URL, decode_responses=True)
    try:
        await asyncio.wait_for(client.ping(), timeout=PROBE_TIMEOUT_SECONDS)
        return True
    except Exception as e:
        logger.warning("Health probe failed", dependency="redis", error=str(e))
        return False
    finally:
        await client.aclose()


def _response(status_line: bytes, payload: dict) -> bytes:
    body = json.dumps(payload).encode()
    return (
        b"HTTP/1.1 " + status_line + b"\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n"
        b"\r\n" + body
    )


async def _handle_client(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        line = await asyncio.wait_for(
            reader.readline(), timeout=REQUEST_LINE_TIMEOUT_SECONDS
        )
        parts = line.decode("latin-1").split()
        path = parts[1].split("?")[0] if len(parts) > 1 else "/"

        if path != "/health":
            writer.write(_response(b"404 Not Found", {"error": "not found"}))
        elif await _redis_is_reachable():
            writer.write(_response(b"200 OK", {"status": "ok", "redis": "ok"}))
        else:
            writer.write(
                _response(
                    b"503 Service Unavailable",
                    {"status": "degraded", "redis": "down"},
                )
            )
        await writer.drain()
    except Exception as e:
        # A failing probe connection must never take down the worker.
        logger.warning("Health request failed", error=str(e))
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def start_health_server(port: int | None = None) -> asyncio.Server:
    """
    Bind and start serving in the background.

    Returns the server so the caller owns its lifetime. Pass port=0 in tests to
    get an ephemeral port from the OS instead of fighting over a fixed one.
    """
    bind_port = get_settings().HEALTH_PORT if port is None else port
    server = await asyncio.start_server(_handle_client, "0.0.0.0", bind_port)
    logger.info("Health server listening", port=server.sockets[0].getsockname()[1])
    return server
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/integration/test_health.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add stdlib asyncio health probe server"
```

---

### Task 7: Worker entry point

**Files:**
- Modify: `main.py` (full rewrite)
- Test: `tests/unit/test_main.py` (rewrite)

**Interfaces:**
- Consumes: `RedisConsumer`, `start_health_server()` (Task 6), `close_producer()`, `close_state_client()` (Task 3), `init_tracing()` (Task 1).
- Produces: `run_worker(stop: asyncio.Event | None = None) -> None`, `main() -> None`, `SHUTDOWN_TIMEOUT_SECONDS: int`.

- [ ] **Step 1: Write the failing tests**

Replace `tests/unit/test_main.py` entirely:

```python
import asyncio

import pytest

import main as main_module


class FakeConsumer:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.closed = False
        self._running = asyncio.Event()

    async def start(self):
        self.started = True
        await self._running.wait()

    async def stop(self):
        self.stopped = True
        self._running.set()

    async def close(self):
        self.closed = True


class FakeServer:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


@pytest.fixture
def fakes(monkeypatch):
    consumer = FakeConsumer()
    server = FakeServer()
    calls = {"producer_closed": False, "state_closed": False}

    async def fake_start_health_server(port=None):
        return server

    async def fake_close_producer():
        calls["producer_closed"] = True

    async def fake_close_state_client():
        calls["state_closed"] = True

    monkeypatch.setattr(main_module, "RedisConsumer", lambda: consumer)
    monkeypatch.setattr(main_module, "start_health_server", fake_start_health_server)
    monkeypatch.setattr(main_module, "close_producer", fake_close_producer)
    monkeypatch.setattr(main_module, "close_state_client", fake_close_state_client)
    return consumer, server, calls


async def test_run_worker_starts_consumer_and_health_server(fakes):
    consumer, server, _ = fakes
    stop = asyncio.Event()

    task = asyncio.create_task(main_module.run_worker(stop=stop))
    await asyncio.sleep(0.05)

    assert consumer.started is True
    assert server.closed is False

    stop.set()
    await asyncio.wait_for(task, timeout=5)


async def test_stop_event_shuts_everything_down_in_order(fakes):
    consumer, server, calls = fakes
    stop = asyncio.Event()

    task = asyncio.create_task(main_module.run_worker(stop=stop))
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=5)

    assert consumer.stopped is True
    assert consumer.closed is True
    assert server.closed is True
    assert calls["producer_closed"] is True
    assert calls["state_closed"] is True


async def test_a_hung_consumer_is_cancelled_rather_than_hanging_shutdown(
    monkeypatch, fakes
):
    """
    stop() asks the loop to finish its current message. If the handler is
    wedged, shutdown must not wait forever — SIGTERM has a deadline before
    the orchestrator sends SIGKILL.
    """
    consumer, _, calls = fakes
    monkeypatch.setattr(main_module, "SHUTDOWN_TIMEOUT_SECONDS", 0.1)

    async def never_stops():
        self_stop_ignored = asyncio.Event()
        await self_stop_ignored.wait()

    monkeypatch.setattr(consumer, "stop", lambda: asyncio.sleep(0))
    monkeypatch.setattr(consumer, "start", never_stops)

    stop = asyncio.Event()
    task = asyncio.create_task(main_module.run_worker(stop=stop))
    await asyncio.sleep(0.05)
    stop.set()

    await asyncio.wait_for(task, timeout=5)
    assert calls["producer_closed"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/unit/test_main.py -v`
Expected: FAIL — `main.py` still builds a FastAPI app and imports `db.postgres.session`, so the import raises `ModuleNotFoundError: No module named 'db'`.

- [ ] **Step 3: Rewrite `main.py`**

```python
# main.py
"""
Worker entry point.

Two coroutines on one event loop: the Redis Streams consumer, and a health
probe server so an orchestrator can ask how it is doing. There is no HTTP API
— this process exists to consume events.
"""

import asyncio
import signal

from config.logging import configure_logging, get_logger
from config.tracing import init_tracing
from health.server import start_health_server
from messaging.consumer import RedisConsumer
from messaging.producer.redis_producer import close_producer
from messaging.state import close_state_client

configure_logging()
init_tracing()

logger = get_logger(__name__)

# How long a handler gets to finish its current message once shutdown starts.
# Keep it under your orchestrator's grace period, or SIGKILL wins the race.
SHUTDOWN_TIMEOUT_SECONDS = 10


def _install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Not available on every platform; Ctrl-C still raises
            # KeyboardInterrupt, which asyncio.run handles.
            pass


async def run_worker(stop: asyncio.Event | None = None) -> None:
    """
    Run until signalled, then shut down without dropping an in-flight message.

    `stop` is injectable so tests can drive shutdown without sending signals.
    """
    stop = stop or asyncio.Event()
    _install_signal_handlers(stop)

    consumer = RedisConsumer()
    consumer_task = asyncio.create_task(consumer.start())
    consumer_task.add_done_callback(
        lambda t: (
            logger.error("Consumer task died", error=str(t.exception()))
            if not t.cancelled() and t.exception()
            else None
        )
    )

    server = await start_health_server()
    logger.info("Worker started")

    # If the consumer dies on its own, stop waiting — a worker whose consumer
    # is dead but whose health server still answers is the worst outcome.
    consumer_task.add_done_callback(lambda _: stop.set())

    await stop.wait()
    logger.info("Shutting down worker")

    await consumer.stop()
    try:
        await asyncio.wait_for(consumer_task, timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning("Consumer did not stop in time; cancelling")
        consumer_task.cancel()
        await asyncio.gather(consumer_task, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        # Whatever killed the consumer must not skip the cleanup below —
        # that would be a resource leak.
        logger.error("Consumer task ended with error", error=str(e))

    server.close()
    await server.wait_closed()

    await consumer.close()
    await close_producer()
    await close_state_client()
    logger.info("Worker stopped; connections closed")


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/unit -v`
Expected: PASS — the whole unit suite, `test_main.py` included.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: replace the FastAPI app with a worker entry point"
```

---

### Task 8: End-to-end trace propagation

**Files:**
- Modify: `messaging/producer/redis_producer.py`, `messaging/consumer/redis_consumer.py:121-168`
- Test: `tests/integration/test_tracing.py` (create)

**Interfaces:**
- Consumes: `traceparent` on `EventEnvelope` (Task 2), the handlers from Tasks 4–5.
- Produces: no new public functions. `RedisProducer.publish` keeps its signature `publish(envelope: EventEnvelope) -> str` — it reads ambient context and never takes a span argument, which is what lets the same producer serve the CLI and the handlers unchanged.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_tracing.py`:

```python
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from messaging.consumer.redis_consumer import RedisConsumer
from messaging.models import EventEnvelope, OrderCreatedEvent
from messaging.producer.redis_producer import RedisProducer, close_producer
from messaging.state import close_state_client

pytestmark = pytest.mark.integration


@pytest.fixture
def spans():
    """
    Install an in-memory exporter.

    trace.get_tracer() returns a proxy that resolves the provider lazily, so
    modules that grabbed a tracer at import time still land here.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()


@pytest.fixture(autouse=True)
async def _close_clients(app_settings):
    yield
    await close_state_client()
    await close_producer()


def by_name(exporter, name):
    return [s for s in exporter.get_finished_spans() if s.name == name]


async def test_publish_injects_traceparent_into_the_envelope(
    app_settings, redis_client, spans
):
    producer = RedisProducer()
    await producer.publish(
        EventEnvelope.create(
            event_type="OrderCreated",
            payload=OrderCreatedEvent(
                order_ref="r1", item="widget", quantity=3, unit_price_cents=450
            ),
            correlation_id="corr-1",
            source="test",
        )
    )
    await producer.close()

    entries = await redis_client.xrange(app_settings.STREAM_NAME)
    published = EventEnvelope.model_validate_json(entries[0][1]["event"])

    assert published.traceparent is not None
    publish_span = by_name(spans, "publish OrderCreated")[0]
    assert format(publish_span.context.trace_id, "032x") in published.traceparent


async def test_the_full_chain_is_one_trace_across_both_hops(
    app_settings, redis_client, spans
):
    """
    The assertion this whole design exists for: cli publish -> consume
    OrderCreated -> publish OrderConfirmed -> consume OrderConfirmed, all in
    one trace, each span parented to the one before it.
    """
    tracer = trace.get_tracer("test")
    producer = RedisProducer()
    with tracer.start_as_current_span("cli.publish"):
        await producer.publish(
            EventEnvelope.create(
                event_type="OrderCreated",
                payload=OrderCreatedEvent(
                    order_ref="r1", item="widget", quantity=3, unit_price_cents=450
                ),
                correlation_id="corr-1",
                source="cli",
            )
        )

    consumer = RedisConsumer()
    await consumer.ensure_group()

    # Two passes: the first handles OrderCreated (which publishes
    # OrderConfirmed), the second handles OrderConfirmed.
    for _ in range(2):
        response = await consumer.redis.xreadgroup(
            groupname=consumer.consumer_group,
            consumername=consumer.consumer_name,
            streams={consumer.stream_name: ">"},
            count=10,
            block=1000,
        )
        for _stream, messages in response or []:
            for message_id, fields in messages:
                await consumer._handle_one(message_id, fields)

    await consumer.close()

    root = by_name(spans, "cli.publish")[0]
    consume_created = by_name(spans, "consume OrderCreated")[0]
    publish_confirmed = by_name(spans, "publish OrderConfirmed")[0]
    consume_confirmed = by_name(spans, "consume OrderConfirmed")[0]

    trace_id = root.context.trace_id
    assert consume_created.context.trace_id == trace_id
    assert publish_confirmed.context.trace_id == trace_id
    assert consume_confirmed.context.trace_id == trace_id

    assert consume_created.parent.span_id == by_name(
        spans, "publish OrderCreated"
    )[0].context.span_id
    assert publish_confirmed.parent.span_id == consume_created.context.span_id
    assert consume_confirmed.parent.span_id == publish_confirmed.context.span_id


async def test_an_envelope_without_traceparent_starts_a_new_trace(
    app_settings, redis_client, spans
):
    consumer = RedisConsumer()
    await consumer.ensure_group()

    envelope = EventEnvelope.create(
        event_type="OrderCreated",
        payload=OrderCreatedEvent(
            order_ref="r2", item="widget", quantity=1, unit_price_cents=100
        ),
        correlation_id="corr-2",
        source="test",
    )
    assert envelope.traceparent is None

    await consumer._handle_one("1-1", {"event": envelope.model_dump_json()})
    await consumer.close()

    span = by_name(spans, "consume OrderCreated")[0]
    assert span.parent is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/integration/test_tracing.py -v`
Expected: FAIL — no spans named `publish OrderCreated` exist yet, so `by_name(...)[0]` raises `IndexError`.

- [ ] **Step 3: Inject context in the producer**

In `messaging/producer/redis_producer.py`, add imports:

```python
from opentelemetry import trace
from opentelemetry.propagate import inject
```

Add below `logger = get_logger(__name__)`:

```python
tracer = trace.get_tracer(__name__)
```

Replace the body of `publish` with:

```python
    async def publish(self, envelope: EventEnvelope) -> str:
        """
        Publish one envelope. Message shape is {"event": "<json>"} — the
        consumer reads the same key.

        Trace context is read from whatever span is CURRENT, not passed in.
        That is deliberate: the same producer is called from the CLI (where the
        current span is the CLI's root) and from inside a handler (where it is
        the span for the message being handled), and both cases chain correctly
        with no argument threading.
        """
        with tracer.start_as_current_span(f"publish {envelope.event_type}"):
            carrier: dict[str, str] = {}
            inject(carrier)
            envelope = envelope.model_copy(
                update={"traceparent": carrier.get("traceparent")}
            )

            try:
                message_id = await self.redis.xadd(
                    name=self.stream_name,
                    fields={"event": envelope.model_dump_json()},
                )
                logger.info(
                    "Event published",
                    event_id=str(envelope.event_id),
                    event_type=envelope.event_type,
                    stream=self.stream_name,
                    message_id=message_id,
                )
                return message_id
            except Exception as e:
                logger.error(
                    "Failed to publish event",
                    event_type=envelope.event_type,
                    error=str(e),
                    exc_info=True,
                )
                raise
```

- [ ] **Step 4: Make the consumer's span current during dispatch**

In `messaging/consumer/redis_consumer.py`, add imports:

```python
from opentelemetry import trace
from opentelemetry.propagate import extract
```

Add below `logger = get_logger(__name__)`:

```python
tracer = trace.get_tracer(__name__)
```

In `_handle_one`, wrap everything from the `log = logger.bind(...)` line to the end of the method in a span. The retry loop and the dead-letter call both belong inside it:

```python
        carrier = {"traceparent": envelope.traceparent} if envelope.traceparent else {}
        parent_context = extract(carrier)

        # start_as_current_span, NOT a detached span. The producer reads
        # ambient context, so making this span current is the entire mechanism
        # by which an event published from inside a handler continues this
        # trace. A detached span logs and exports identically and silently
        # orphans every downstream hop — which is why test_tracing.py asserts
        # on parent span ids rather than on spans merely existing.
        with tracer.start_as_current_span(
            f"consume {envelope.event_type}", context=parent_context
        ):
            log = logger.bind(
                message_id=message_id,
                event_id=str(envelope.event_id),
                event_type=envelope.event_type,
                correlation_id=envelope.correlation_id,
            )

            last_error = ""
            for attempt in range(1, self.max_retries + 1):
                try:
                    await dispatch_event(envelope)
                    await self.redis.xack(
                        self.stream_name, self.consumer_group, message_id
                    )
                    log.debug("Message handled and acked", attempt=attempt)
                    return
                except Exception as e:
                    last_error = f"{e}\n{traceback.format_exc()}"
                    log.warning(
                        "Handler failed",
                        attempt=attempt,
                        max_retries=self.max_retries,
                        error=str(e),
                    )
                    if attempt < self.max_retries:
                        backoff = self.retry_backoff_ms * (2 ** (attempt - 1)) / 1000
                        await asyncio.sleep(backoff)

            await self._dead_letter(
                message_id, fields, "handler_error", last_error, self.max_retries
            )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/integration/test_tracing.py -v`
Expected: PASS (3 tests)

If `test_the_full_chain_is_one_trace_across_both_hops` proves flaky under pytest-asyncio's per-test event loops, the spec's agreed fallback (Risks section) is to assert on the `traceparent` field of the published `OrderConfirmed` envelope instead — it still catches a detached span, because a detached span produces a different span id in the carrier. Take the fallback only if the span assertions are genuinely unstable, not on a first failure.

- [ ] **Step 6: Run the full suite**

Run: `poetry run pytest -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: propagate trace context through the stream, end to end"
```

---

### Task 9: CLI publisher

**Files:**
- Create: `cli.py`
- Test: `tests/integration/test_cli.py` (create)

**Interfaces:**
- Consumes: `EventEnvelope`, `OrderCreatedEvent` (Task 2), `RedisProducer` (Task 8), `format_cents()` (Task 2).
- Produces: `build_parser() -> argparse.ArgumentParser`, `publish(args) -> list[str]`, `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_cli.py`:

```python
import pytest

import cli
from messaging.models import EventEnvelope, OrderCreatedEvent
from messaging.producer.redis_producer import close_producer

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _close_clients(app_settings):
    yield
    await close_producer()


async def test_publish_writes_one_envelope_per_count(app_settings, redis_client):
    args = cli.build_parser().parse_args(
        [
            "publish",
            "--ref", "demo-1",
            "--item", "widget",
            "--quantity", "3",
            "--unit-price-cents", "450",
            "--count", "2",
        ]
    )

    message_ids = await cli.publish(args)

    assert len(message_ids) == 2
    entries = await redis_client.xrange(app_settings.STREAM_NAME)
    assert len(entries) == 2

    envelope = EventEnvelope.model_validate_json(entries[0][1]["event"])
    assert envelope.event_type == "OrderCreated"
    assert envelope.source == "cli"
    assert envelope.correlation_id == "demo-1"
    assert envelope.traceparent is not None
    assert isinstance(envelope.payload, OrderCreatedEvent)
    assert envelope.payload.unit_price_cents == 450
    assert envelope.payload.quantity == 3


def test_count_defaults_to_one():
    args = cli.build_parser().parse_args(
        ["publish", "--ref", "r", "--item", "i", "--quantity", "1",
         "--unit-price-cents", "1"]
    )
    assert args.count == 1


def test_negative_unit_price_is_rejected_by_the_parser():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(
            ["publish", "--ref", "r", "--item", "i", "--quantity", "1",
             "--unit-price-cents", "-1"]
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/integration/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cli'`

- [ ] **Step 3: Write `cli.py`**

```python
# cli.py
"""
The producer side of the sample, as a one-shot command.

Publishing lives in a CLI rather than an HTTP endpoint because this template
has no HTTP surface: a worker consumes events, and something else produces
them. Run it twice with the same --ref to watch the consumer's idempotency
guard turn the second delivery into a logged no-op.

    python -m cli publish --ref demo-1 --item widget \\
                          --quantity 3 --unit-price-cents 450 --count 2
"""

import argparse
import asyncio
import sys

from opentelemetry import trace

from config.logging import configure_logging
from config.tracing import init_tracing
from messaging.models import EventEnvelope, OrderCreatedEvent
from messaging.producer.redis_producer import RedisProducer
from money import format_cents

configure_logging()
init_tracing()

tracer = trace.get_tracer(__name__)


def non_negative_int(raw: str) -> int:
    value = int(raw)
    if value < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return value


def positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be one or greater")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    publish_parser = sub.add_parser("publish", help="Publish an OrderCreated event")
    publish_parser.add_argument("--ref", required=True, help="Order reference")
    publish_parser.add_argument("--item", default="widget")
    publish_parser.add_argument("--quantity", type=positive_int, default=1)
    publish_parser.add_argument(
        "--unit-price-cents",
        type=non_negative_int,
        default=450,
        help="Unit price in integer minor units: 450 means 4.50",
    )
    publish_parser.add_argument(
        "--count",
        type=positive_int,
        default=1,
        help="Publish the same event N times, to demonstrate idempotency",
    )
    return parser


async def publish(args: argparse.Namespace) -> list[str]:
    """Publish `count` copies of one OrderCreated event; return message ids."""
    producer = RedisProducer()
    message_ids: list[str] = []
    try:
        for _ in range(args.count):
            # The CLI process is the root of the distributed trace. Without
            # this span the publish still works, but its context has no parent
            # and the worker's spans start a trace that begins mid-pipeline.
            with tracer.start_as_current_span("cli.publish"):
                message_ids.append(
                    await producer.publish(
                        EventEnvelope.create(
                            event_type="OrderCreated",
                            payload=OrderCreatedEvent(
                                order_ref=args.ref,
                                item=args.item,
                                quantity=args.quantity,
                                unit_price_cents=args.unit_price_cents,
                            ),
                            correlation_id=args.ref,
                            source="cli",
                        )
                    )
                )
    finally:
        await producer.close()
    return message_ids


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    message_ids = asyncio.run(publish(args))

    total = args.quantity * args.unit_price_cents
    print(
        f"published {len(message_ids)} x OrderCreated "
        f"ref={args.ref} qty={args.quantity} "
        f"unit={format_cents(args.unit_price_cents)} "
        f"expected_total={format_cents(total)}"
    )
    for message_id in message_ids:
        print(f"  {message_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/integration/test_cli.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add the CLI event publisher"
```

---

### Task 10: Packaging, demo, and the full round trip

**Files:**
- Modify: `Dockerfile`, `docker-compose.yaml`, `Makefile`, `.env.example`
- Test: `tests/integration/test_order_roundtrip.py` (rewrite)

**Interfaces:**
- Consumes: everything from Tasks 1–9.
- Produces: `make up` / `make demo` / `make logs` targets; a `worker` compose service.

- [ ] **Step 1: Write the failing round-trip test**

Replace `tests/integration/test_order_roundtrip.py` entirely:

```python
import asyncio

import pytest

import cli
from messaging.consumer.redis_consumer import RedisConsumer
from messaging.models import EventEnvelope, OrderConfirmedEvent
from messaging.producer.redis_producer import close_producer
from messaging.state import close_state_client

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _close_clients(app_settings):
    yield
    await close_state_client()
    await close_producer()


async def drain(consumer: RedisConsumer, passes: int = 2) -> None:
    """Read and handle whatever is pending, `passes` times."""
    for _ in range(passes):
        response = await consumer.redis.xreadgroup(
            groupname=consumer.consumer_group,
            consumername=consumer.consumer_name,
            streams={consumer.stream_name: ">"},
            count=10,
            block=500,
        )
        for _stream, messages in response or []:
            for message_id, fields in messages:
                await consumer._handle_one(message_id, fields)


async def test_cli_publish_flows_through_both_hops(app_settings, redis_client):
    """
    The whole pipeline: CLI publishes OrderCreated twice, the consumer confirms
    once, computes the total, publishes exactly one OrderConfirmed, and handles
    that too. Two events in, one event out.
    """
    args = cli.build_parser().parse_args(
        ["publish", "--ref", "demo-1", "--item", "widget", "--quantity", "3",
         "--unit-price-cents", "450", "--count", "2"]
    )
    await cli.publish(args)

    consumer = RedisConsumer()
    await consumer.ensure_group()
    await drain(consumer, passes=3)
    await consumer.close()

    stored = await redis_client.hgetall("order:demo-1")
    assert stored["status"] == "confirmed"
    assert stored["total_cents"] == "1350"

    entries = await redis_client.xrange(app_settings.STREAM_NAME)
    confirmed = [
        EventEnvelope.model_validate_json(fields["event"])
        for _id, fields in entries
        if EventEnvelope.model_validate_json(fields["event"]).event_type
        == "OrderConfirmed"
    ]
    assert len(confirmed) == 1
    assert isinstance(confirmed[0].payload, OrderConfirmedEvent)
    assert confirmed[0].payload.total_cents == 1350

    pending = await redis_client.xpending(
        app_settings.STREAM_NAME, app_settings.CONSUMER_GROUP
    )
    assert pending["pending"] == 0, "every message must be acked"


async def test_nothing_lands_in_the_dlq_on_the_happy_path(app_settings, redis_client):
    args = cli.build_parser().parse_args(
        ["publish", "--ref", "demo-2", "--item", "widget", "--quantity", "1",
         "--unit-price-cents", "1000"]
    )
    await cli.publish(args)

    consumer = RedisConsumer()
    await consumer.ensure_group()
    await drain(consumer, passes=3)
    await consumer.close()

    assert await redis_client.xlen(app_settings.dlq_stream) == 0
    await asyncio.sleep(0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/integration/test_order_roundtrip.py -v`
Expected: FAIL — the existing file imports the deleted `OrderService`, so collection errors.

Note: once Tasks 1–9 are done the new test body may pass immediately. That is fine — it is a regression test over already-built parts, and Step 2's failure is the collection error from the old file.

- [ ] **Step 3: Run test to verify it passes**

Run: `poetry run pytest tests/integration/test_order_roundtrip.py -v`
Expected: PASS (2 tests)

- [ ] **Step 4: Update the Dockerfile**

Replace the last four lines (`EXPOSE`, the `COPY docker-entrypoint.sh`, `RUN chmod`, and `ENTRYPOINT`) with:

```dockerfile
EXPOSE 8000

CMD ["python", "main.py"]
```

- [ ] **Step 5: Rewrite `docker-compose.yaml`**

```yaml
services:
  worker:
    build: .
    container_name: pmt_worker
    ports:
      - "8000:8000"
    environment:
      ENVIRONMENT: development
      HEALTH_PORT: 8000
      REDIS_STREAM_URL: redis://:redis@redis:6379/1
      STREAM_NAME: order.events
      CONSUMER_GROUP: order_service_v1
      STREAM_POLL_INTERVAL_MS: 1000
      STATE_TTL_SECONDS: 3600
      LOG_LEVEL: INFO
      JSON_LOGS: "true"
      OTEL_EXPORTER_OTLP_ENDPOINT:
      OTEL_EXPORTER_OTLP_ENDPOINT_ENABLE_FALLBACK: "False"
    volumes:
      - .:/app
    depends_on:
      redis:
        condition: service_healthy

  redis:
    image: redis:7
    container_name: pmt_redis
    ports:
      - "6379:6379"
    command: redis-server --requirepass "redis"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "redis", "ping"]
      interval: 2s
      timeout: 3s
      retries: 15
```

- [ ] **Step 6: Rewrite the Makefile**

```makefile
.PHONY: up down logs test test-all lint fmt demo health

up:                ## Start Redis and the worker
	docker compose up --build -d
	@echo "Worker health on http://localhost:8000/health"

down:
	docker compose down

logs:
	docker compose logs -f worker

health:
	@curl -s -i http://localhost:8000/health

test:              ## Unit tests only — no Docker required
	poetry run pytest -m "not integration" --junitxml=reports/junit.xml --cov=. --cov-report=xml:reports/coverage.xml --cov-report=html:reports/htmlcov

test-all:          ## Everything, including testcontainers
	poetry run pytest --junitxml=reports/junit.xml --cov=. --cov-report=xml:reports/coverage.xml --cov-report=html:reports/htmlcov

lint:
	poetry run ruff check .

fmt:
	poetry run black . && poetry run ruff check --fix .

demo:              ## Publish one order twice; watch it confirm exactly once
	@echo "--- publishing OrderCreated x2 (same ref)"
	@docker compose exec worker python -m cli publish \
		--ref demo-1 --item widget --quantity 3 --unit-price-cents 450 --count 2
	@echo "--- waiting for the consumer..."
	@sleep 3
	@echo "--- state in Redis"
	@docker compose exec redis redis-cli -a redis --no-auth-warning HGETALL order:demo-1
	@echo "--- worker log (one confirm, one already-processed, one confirmation received)"
	@docker compose logs --tail=30 worker
```

- [ ] **Step 7: Rewrite `.env.example`**

```
ENVIRONMENT=development

# Health probe server
HEALTH_PORT=8000

# Redis Streams
REDIS_STREAM_URL=redis://localhost:6379/1
STREAM_NAME=order.events
CONSUMER_GROUP=order_service_v1
STREAM_POLL_INTERVAL_MS=1000

# Consumer reliability
CONSUMER_BATCH_SIZE=10
CONSUMER_MAX_RETRIES=3
CONSUMER_RETRY_BACKOFF_MS=500
CONSUMER_CLAIM_MIN_IDLE_MS=60000
DLQ_STREAM_NAME=

# Handler state store
STATE_TTL_SECONDS=3600

# Logging
LOG_LEVEL=INFO
JSON_LOGS=false

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_EXPORTER_OTLP_ENDPOINT_ENABLE_FALLBACK=False
```

- [ ] **Step 8: Verify the demo end to end**

```bash
make down || true
make up
sleep 5
make health
make demo
```

Expected: `make health` prints `HTTP/1.1 200 OK` and `{"status": "ok", "redis": "ok"}`. `make demo` prints two message ids, then a hash containing `total_cents 1350`, then worker logs containing exactly one `Order confirmed`, one `Order already processed; nothing to do`, and one `Order confirmation received`.

- [ ] **Step 9: Commit**

```bash
make down
git add -A
git commit -m "build: worker container, redis-only compose, and the make demo flow"
```

---

### Task 11: Documentation

**Files:**
- Modify: `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: everything. No code changes.

- [ ] **Step 1: Rewrite `README.md`**

Replace the content down to the end of "Make it yours" with:

````markdown
# Python Microservice Template — Redis Streams

An async worker template with a working reference pipeline: a CLI publishes an
event, a consumer picks it up, computes a result, and publishes a follow-on
event — all under one distributed trace. Read it end to end, then replace the
sample events with your own.

There is no HTTP API and no database. This is a message-processing service.

---

## Quickstart

```bash
make up      # docker compose up --build -d; starts Redis and the worker
make demo    # publish one order twice; watch it confirm exactly once
```

Expected output:

```
--- publishing OrderCreated x2 (same ref)
published 2 x OrderCreated ref=demo-1 qty=3 unit=4.50 expected_total=13.50
  1735300000000-0
  1735300000000-1
--- waiting for the consumer...
--- state in Redis
status
confirmed
item
widget
quantity
3
total_cents
1350
--- worker log
... "Order confirmed" total=13.50
... "Order already processed; nothing to do"
... "Order confirmation received" total=13.50
```

Two events in, one confirmation out. The second delivery is a logged no-op —
that is the idempotency guard doing its job, not a bug.

---

## What the demo does

```
python -m cli publish --ref demo-1 --quantity 3 --unit-price-cents 450 --count 2
  └→ XADD order.events "OrderCreated"   x2

[worker] XREADGROUP → OrderCreated (1st)
  └→ HSETNX order:demo-1 status confirmed → 1
  └→ total_cents = 3 * 450 = 1350        [the processing step]
  └→ XADD order.events "OrderConfirmed" {total_cents: 1350}
  └→ XACK

[worker] XREADGROUP → OrderCreated (2nd)
  └→ HSETNX → 0 → "already processed", publishes nothing
  └→ XACK

[worker] XREADGROUP → OrderConfirmed
  └→ log; XACK
```

The consumer is both a consumer and a producer. That middle hop is the point of
the template: consume → compute → publish is the shape most real services take.

---

## One trace across both hops

Trace context rides in a `traceparent` field on the envelope. The producer
injects whatever span is current; the consumer extracts it and makes its
message span current, so anything a handler publishes is automatically a child
of the message being handled:

```
[cli.publish]                              (cli process, root)
  └── [publish OrderCreated]
        └── [consume OrderCreated]         (worker)
              └── [publish OrderConfirmed]
                    └── [consume OrderConfirmed]
```

Point `OTEL_EXPORTER_OTLP_ENDPOINT` at a collector to see it, or set
`OTEL_EXPORTER_OTLP_ENDPOINT_ENABLE_FALLBACK=True` to dump spans to the console.

The single rule to preserve if you touch this: the consumer's span must be
made **current** (`start_as_current_span`), not held detached. A detached span
looks identical in the logs and silently orphans every downstream hop.

---

## Health

The worker serves one endpoint, on `HEALTH_PORT` (8000 in compose):

```bash
make health     # 200 {"status":"ok","redis":"ok"} or 503 {"status":"degraded",...}
```

It is about forty lines of `asyncio.start_server` in `health/server.py`, not a
web framework. There is no `/info` — `SERVICE_NAME`, `SERVICE_VERSION` and
`ENVIRONMENT` are stamped on every exported span as resource attributes, so
the collector already has them.

---

## Money

Amounts are integer minor units everywhere: `450` means `4.50`, and the field
name carries the unit (`unit_price_cents`, `total_cents`). Never floats.
Formatting to a human-readable string happens only at output edges, via
`format_cents()` in `money.py` — payload models carry ints, so the wire format
never depends on presentation.

---

## What this template does not solve

The handler writes its state and then publishes. Those two steps are not
atomic: if the publish fails after the state write, the retry sees the
idempotency guard and skips the publish, so the downstream event is lost. This
is the write-then-publish problem, and the real answer is a transactional
outbox — persist the outgoing event in the same write as the state, and let a
separate relay drain it to the stream.

That is deliberately not implemented here. It roughly doubles the moving parts,
and a template's job is to make the mechanism legible. The failure is named in
`messaging/consumer/handlers/order_created.py` so nobody meets it by surprise.

---

## Make it yours

The sample events exist to be replaced. Edit these four places, in order:

1. `messaging/models/events/` — your payloads, in place of `OrderCreatedEvent`
   and `OrderConfirmedEvent`.
2. `messaging/models/envelope.py` — add your event types to the `Literal` and
   to the `EventPayload` union.
3. `messaging/consumer/handlers/` — your handlers.
4. `messaging/consumer/dispatcher.py` — register them in `HANDLERS`.

`OrderConfirmed` is a worked example of exactly that four-file edit; follow it.

Two rules to keep when you do:

- **Handlers must be idempotent.** Redis Streams delivers at least once.
  Guard with a conditional write, and put the early return *before* any
  publish — otherwise one redelivery amplifies through every downstream
  consumer.
- **Do not publish upstream from a handler.** Both sample events share one
  stream; a handler that republishes what it consumes is an infinite loop that
  looks like a busy worker.
````

Keep any sections after "Make it yours" that still apply (licence, contributing). Delete any that reference the API, Postgres, or migrations.

- [ ] **Step 2: Update `CLAUDE.md`**

Make these edits:

1. **Project Overview** — replace with: a Redis Streams worker template shipping a reference pipeline (CLI publishes `OrderCreated`, consumer computes a total and publishes `OrderConfirmed`), with no HTTP API and no database.
2. **Development Commands** — delete `make migrate` and `make revision`; change `make up` to "starts Redis and the worker", `make logs` to "tail the worker container's logs", `make demo` to "publish an order twice, watch it confirm once"; add `make health`.
3. **Running the application locally** — replace the uvicorn instructions with `python main.py` for the worker and `python -m cli publish ...` for the producer. Delete the paragraph about port 8099 and the migrations warning; note that `HEALTH_PORT` defaults to 8000 and that no configuration is required at all.
4. **Architecture / Layered Structure** — delete layers 1 (API), 2 (Core), and 3 (Data Access). Renumber so Messaging is 1 and Configuration is 2. Add `health/server.py`, `cli.py`, `money.py` and `messaging/state.py` to the descriptions.
5. **Application Entry Point** — replace the FastAPI lifespan description with: `main.py` runs `run_worker()`, which starts `RedisConsumer` and the health server on one loop, installs SIGINT/SIGTERM handlers, and on shutdown stops the consumer with a `SHUTDOWN_TIMEOUT_SECONDS` deadline before closing the consumer, producer and state clients.
6. **Configuration System** — remove `DATABASE_URL` and `SERVICE_PORT`; add `HEALTH_PORT` and `STATE_TTL_SECONDS`; note there are no required settings.
7. **Observability** — add: the FastAPI auto-instrumentation is gone; spans are explicit; trace context crosses the stream in `EventEnvelope.traceparent`; the consumer's message span must be made current with `start_as_current_span` so handler publishes chain.
8. **Router Pattern** and **Health Check Pattern** — delete the router section; rewrite health as: one endpoint on a stdlib asyncio server, Redis `PING` with a 2s timeout, 503 when it fails.
9. **Migrations** — delete the entire section.
10. **Consumer** — keep it. Restate the idempotency example in terms of `HSETNX` rather than the SQL `UPDATE`, and add the rule that a redelivery must not publish a downstream event. Update the "New event types" instructions to the four-file list from the README.
11. Add a **Money** subsection under Code Style: integer minor units, `_cents` suffix, `format_cents()` at output edges only.

- [ ] **Step 3: Verify the docs match reality**

```bash
grep -rniE "fastapi|uvicorn|postgres|alembic|sqlalchemy|/docs|/info|8099|migrate" \
  README.md CLAUDE.md Makefile docker-compose.yaml .env.example Dockerfile
```

Expected: no hits except deliberate historical mentions. Investigate every hit.

- [ ] **Step 4: Full verification**

```bash
make lint
make test
make test-all
```

Expected: lint clean, both suites pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs: rewrite README and CLAUDE.md for the Redis-only template"
```
