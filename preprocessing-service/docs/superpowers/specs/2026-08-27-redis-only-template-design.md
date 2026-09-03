# Redis-Only Template — Design

Date: 2026-08-27
Branch: `redis-only-template`
Status: approved, ready for implementation planning

## Goal

Reduce the microservice template to one thing: a Redis Streams producer and
consumer. The HTTP API and PostgreSQL layers are removed entirely. What
remains is a worker process that consumes events, a CLI that publishes them,
and the envelope/dispatcher/handler machinery between them.

The template's teaching value must survive the strip. Specifically:
at-least-once delivery, idempotent handlers, retry, dead-lettering,
`XAUTOCLAIM` recovery, a validated envelope as the single schema boundary, and
an unbroken distributed trace across every process hop.

## Non-goals

- No HTTP API, no request/response layer, no OpenAPI docs.
- No relational database, no ORM, no migrations.
- No new domain. The `OrderCreated` sample event is retained; a second event,
  `OrderConfirmed`, is added solely to make the consumer-as-producer hop real.

## Architecture

Two processes over one Docker image:

- **Worker** (`main.py`) — long-running. Runs the `RedisConsumer` loop and a
  minimal health server concurrently on one event loop.
- **CLI** (`cli.py`) — one-shot. Builds an `EventEnvelope` and publishes it via
  the existing `RedisProducer`.

Redis serves three roles: the event stream, the dead-letter stream, and the
handler's state store. No other infrastructure.

### Package layout

Existing flat top-level packages are retained (`messaging/`, `config/`); no
imports move. Two additions:

- `health/server.py` — the stdlib asyncio health server.
- `cli.py` — the publisher CLI, at the repo root, invoked `python -m cli`.

## Component design

### 1. Entry point (`main.py`)

Replaces the FastAPI app. Responsibilities:

- `configure_logging()` and `init_tracing()` on import, as today.
- `asyncio.run()` over `gather(consumer.start(), serve_health())`.
- Install SIGINT/SIGTERM handlers that trigger the same graceful shutdown the
  current lifespan performs: `consumer.stop()`, await the task with a 10s
  timeout before cancelling, `consumer.close()`, `close_producer()`.
- No `close_db()` — `db/` is gone.

The worker holds the process-wide producer as well as the consumer, because
handlers publish (see §5).

### 2. Health server (`health/server.py`)

`asyncio.start_server` on `settings.HEALTH_PORT`. Reads the request line,
ignores everything else, and responds:

- `GET /health` → Redis `PING` with a 2-second timeout. `200` with
  `{"status":"ok","redis":"ok"}`, or `503` with
  `{"status":"degraded","redis":"down"}`.
- Any other path → `404`.

Connection: `Connection: close` on every response; no keep-alive handling. This
is a probe endpoint, not a web framework, and the code should say so in a
docstring.

There is no `/info` endpoint — see §7.

### 3. CLI (`cli.py`)

`argparse`, no new dependency.

```
python -m cli publish --ref demo-1 --item widget --quantity 3 \
                      --unit-price-cents 450 [--count N]
```

Builds `EventEnvelope.create(event_type="OrderCreated", ..., source="cli")` and
publishes each one, printing the returned stream message id. `--count` repeats
the same ref, which is what makes the idempotency demo visible. Closes the
producer before exiting.

Each publish is wrapped in a `cli.publish` span, so the CLI process is the root
of the distributed trace rather than an orphan (§5).

### 4. Events and handlers

Two event types, and the second exists to prove the trace crosses processes.

**`OrderCreated`** (`messaging/models/events/order_created.py`) — the existing
payload plus one field: `order_ref`, `item`, `quantity`, `unit_price_cents`.
These are the *inputs* to the processing step.

**`OrderConfirmed`** (`messaging/models/events/order_confirmed.py`) — new, and
carries the *output*: `order_ref`, `total_cents`, `confirmed_at`.

**Money is integer minor units throughout.** `unit_price_cents` and
`total_cents` are `int`, and `1000` means `10.00`. Never `float` — binary
floats cannot represent money exactly, and a template people copy should not
teach otherwise. Integers also serialise to JSON as themselves, so no
precision question arises anywhere on the wire, in Redis, or in a consumer
written in another language.

The `_cents` suffix is part of the lesson: the unit lives in the field name, so
no reader has to guess the scale of a bare `price`. Formatting for humans
(`1350 → "13.50"`) happens only at the edges — a `format_cents()` helper used
by the CLI's output and the handler's log line, never in the payload models
themselves.

Both are added to the `Literal` and the `EventPayload` union in
`messaging/models/envelope.py`, and both get a row in `HANDLERS` in
`messaging/consumer/dispatcher.py`. The `EventPayload` union stops being a bare
alias and becomes a real union, which is the shape the README's extension
instructions describe.

#### `OrderCreated` handler

Replaces the SQL `UPDATE ... WHERE status='pending'` with a conditional Redis
write that preserves the same semantics, then publishes the follow-on event.

```python
key = f"order:{payload.order_ref}"
first = await r.hsetnx(key, "status", "confirmed")
if not first:
    log.info("Order already processed; nothing to do")
    return                      # NOTE: returns before publishing

# the processing step — int arithmetic, exact by construction
total_cents = payload.quantity * payload.unit_price_cents
confirmed_at = datetime.now(UTC)

await r.hset(key, mapping={"item": ..., "quantity": ...,
                           "total_cents": total_cents,
                           "confirmed_at": confirmed_at.isoformat()})
await r.expire(key, settings.STATE_TTL_SECONDS)
await get_producer().publish(
    EventEnvelope.create(
        "OrderConfirmed",
        OrderConfirmedEvent(order_ref=..., total_cents=total_cents,
                            confirmed_at=confirmed_at),
        source="consumer",
    )
)
log.info("Order confirmed", total=format_cents(total_cents))
```

The multiplication is deliberately trivial, but it is real: the outbound event
carries a value that did not exist on the inbound one, so the pipeline is
consume → *compute* → publish rather than consume → relabel → publish. Whatever
replaces this handler slots into the same three positions.

The early return on redelivery is the load-bearing detail: a duplicate
`OrderCreated` must not emit a duplicate `OrderConfirmed`. Idempotency here is
not only about local state, it is about not amplifying redeliveries downstream.
This must be asserted by a test, not just commented.

The handler owns its own Redis client for state, distinct from the consumer's —
this mirrors, and the docstring should carry over, the current lesson that a
handler has no ambient request context and must acquire its own resources.

Known non-atomicity, to be documented in the docstring rather than engineered
around: `HSETNX` followed by `EXPIRE` is two round trips, so a crash between
them leaves a key with no TTL. Acceptable for a demo store; the comment names
a Lua script or `SET NX` as the atomic alternative.

#### `OrderConfirmed` handler

Logs the confirmed order and its total (formatted for humans), and stops. Deliberately side-effect-free: it is the
terminal hop, and its docstring points at the `OrderCreated` handler for the
idempotency pattern rather than duplicating the `HSETNX` machinery. It must
never publish `OrderCreated` — the docstring says so, because a cycle on a
single stream is the obvious way for someone extending this template to hang
their worker.

### 5. Tracing — end-to-end, in both directions

FastAPI auto-instrumentation is removed, so trace continuity becomes explicit
and becomes a first-class feature of the template rather than a leftover.

- `EventEnvelope` gains `traceparent: str | None = None`.
- `RedisProducer.publish` injects the **current** context via the OTel W3C
  propagator into that field. It reads ambient context; it never takes a span
  argument. This is what makes the same producer work unchanged whether it is
  called from the CLI or from inside a handler.
- `RedisConsumer` extracts `traceparent` and opens the per-message span with
  that as its parent.
- **The per-message span MUST be the active context for the duration of
  dispatch** — `with tracer.start_as_current_span(...)`, not a detached span.
  A detached span still logs and still exports; it just silently orphans
  everything the handler publishes. Because the producer reads ambient context,
  this one line is the entire mechanism by which the consumer forwards the
  trace to the next hop.

Resulting trace for `make demo`, one trace with two process hops:

```
[cli.publish]                                  (cli process, root)
  └── [consume OrderCreated]                   (worker) parent = cli.publish
        └── [publish OrderConfirmed]           (worker) parent = consume
              └── [consume OrderConfirmed]     (worker) parent = publish
```

`extra="forbid"` on the envelope is unchanged, and `traceparent` is optional,
so an envelope published without it still validates and simply starts a new
trace.

This is no longer optional scope. The chain in §4 exists to demonstrate it, and
a test asserts the parenting rather than merely asserting spans exist.

### 6. Settings (`config/settings.py`)

- Removed: `DATABASE_URL`. It is the only required field today; without it the
  template runs with zero configuration.
- Added: `HEALTH_PORT: int = 8000`, `STATE_TTL_SECONDS: int = 3600`.
- Retained unchanged: all `REDIS_*`, `STREAM_*`, `CONSUMER_*`, `DLQ_*`,
  logging, and OTEL settings.
- `SERVICE_PORT` is removed in favour of `HEALTH_PORT`, which names what it
  actually binds.
- `SERVICE_NAME`, `SERVICE_VERSION` and `ENVIRONMENT` are retained. Their only
  remaining consumer is the OTel `Resource` (§7).

### 7. `/info` is removed, not ported

`api/routes/info.py` returned `SERVICE_NAME`, `SERVICE_VERSION` and
`ENVIRONMENT`. `config/tracing.py` already stamps exactly those three values on
every span as `service.name`, `service.version` and `deployment.environment`.
The endpoint duplicated a resource attribute set the service ships anyway, so
it is deleted and the spec records where the data now lives: on every exported
span, queryable in the collector, without an HTTP round trip.

## Deletions

Trees: `api/`, `core/`, `db/`.
Files: `alembic.ini`, `docker-entrypoint.sh`, `config/request_logger.py`.
Dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `alembic`,
`opentelemetry-instrumentation-fastapi`, `testcontainers` Postgres extra.
Compose: the `db` service, the `pmt_pgdata` volume, `DATABASE_URL`.
Makefile: `migrate`, `revision`; `up`/`demo` rewritten.
Dockerfile: entrypoint becomes `CMD ["python", "main.py"]`.

`config/tracing.py` keeps `init_tracing()` but drops its `app` parameter and
the `FastAPIInstrumentor` import along with it.

## Data flow

```
$ make demo
  python -m cli publish --ref demo-1 --quantity 3 --unit-price-cents 450 --count 2
    └→ XADD order.events OrderCreated  (traceparent injected)   x2

[worker] XREADGROUP → OrderCreated (1st copy)
  └→ span parented to cli.publish, made current
  └→ HSETNX order:demo-1 status confirmed  → 1
  └→ total_cents = 3 * 450 = 1350 → stored on the hash → "Order confirmed"
  └→ XADD order.events OrderConfirmed {total_cents: 1350}  (traceparent = span)
  └→ XACK

[worker] XREADGROUP → OrderCreated (2nd copy)
  └→ HSETNX → 0 → "Order already processed"; NO OrderConfirmed published
  └→ XACK

[worker] XREADGROUP → OrderConfirmed
  └→ span parented to the handler's publish span
  └→ log; XACK

$ redis-cli HGETALL order:demo-1
  status confirmed  item widget  quantity 3  total_cents 1350  confirmed_at ...
```

Note the asymmetry the demo makes visible: two `OrderCreated` in, one
`OrderConfirmed` out.

## Error handling

Unchanged from the current consumer, and this is deliberate — the reliability
machinery is the point of the template:

- Envelope validation failure → dead-letter immediately, no retries.
- Handler exception → retry up to `CONSUMER_MAX_RETRIES` with exponential
  backoff, then dead-letter with error, traceback, delivery count, and failure
  time; ack either way.
- `XAUTOCLAIM` on start and on every empty poll; a reclaimed message already
  past the retry ceiling is dead-lettered directly.
- CLI publish failure → non-zero exit with the error printed. There is no row
  to be inconsistent with any more, so the "committed but unpublished" caveat
  that `OrderService` documented disappears along with the service.

New case: if the `OrderCreated` handler's `HSETNX` succeeds but the
`OrderConfirmed` publish fails, the handler raises and the message is retried.
The retry finds `HSETNX` returning 0 and takes the early-return path, so the
`OrderConfirmed` event is never published. The state is correct and the
downstream event is lost. This is the same non-atomic write-then-publish
problem `OrderService` documented, in a new place; the docstring names it and
points at the transactional-outbox pattern, and the README keeps that
discussion. It is documented, not solved — solving it is out of scope for a
template.

## Testing

`tests/conftest.py` loses the Postgres container, `migrated_db`,
`reset_engine_globals`, `_reset_session_maker_globals`, and `db_session` — a
substantial simplification. The Redis container fixture and `app_settings`
remain.

- Deleted: `test_migrations.py`, `test_order_repository.py`,
  `test_order_routes.py`, `test_order_service.py`.
- Rewritten: `test_health.py` (health server against reachable and unreachable
  Redis), `test_order_created_handler.py` (fresh key confirms, computes
  `total_cents`, stores it and publishes `OrderConfirmed` carrying it;
  **replay is a no-op that publishes nothing**; a case asserts the total is an
  exact `int` after the JSON round trip, and that a non-integer
  `unit_price_cents` is rejected by envelope validation rather than silently
  coerced),
  `test_order_roundtrip.py` (CLI publish → both hops → key state),
  `test_main.py` (worker starts both tasks; signal triggers graceful shutdown).
- New: `test_order_confirmed_handler.py`; `test_tracing.py` — with an
  in-memory span exporter, assert the full parent chain of §5, including that a
  publish issued from inside a handler is a child of that handler's message
  span. This is the test that would catch a detached-span regression.
- Updated: `test_envelope.py` (both event types, `traceparent` optional),
  `test_dispatcher.py` (two registered handlers).
- Unchanged: `test_redis_consumer.py`, `test_producer.py`.

The unit/integration marker split and the `make test` / `make test-all`
targets are unchanged.

## Documentation

- **README.md** — rewritten around the worker and CLI. The quickstart becomes
  `make up` / `make demo`; the expected output is worker log lines and a
  `HGETALL`, not JSON responses. Gains a short section on the trace chain with
  the span tree from §5. "Make it yours" shrinks from seven files to four:
  `messaging/models/events/`, `messaging/models/envelope.py`,
  `messaging/consumer/handlers/`, `messaging/consumer/dispatcher.py` — and
  `OrderConfirmed` now serves as the worked example of that exact four-file
  edit. It also notes the minor-units convention, since that is the one payload
  decision a reader is most likely to carry into their own domain.
- **CLAUDE.md** — Architecture loses layers 1–3 (API, Core, Data Access) and
  gains the worker/CLI entry points; the Migrations section is deleted whole;
  Development Commands loses `migrate` and `revision`. The Consumer section
  survives nearly intact, with the idempotency example restated in terms of
  `HSETNX` and extended with the "do not amplify redeliveries" rule. The
  Observability section gains the active-context requirement.
- **.env.example** — `DATABASE_URL` removed, `HEALTH_PORT` and
  `STATE_TTL_SECONDS` added.

## Risks

- **Cycle risk.** Two event types on one stream with a handler that publishes
  makes an event cycle possible for anyone extending the template. Mitigated by
  docstring and README warnings, not by code.
- **Trace assertions are the fragile part of the test suite.** The span-parenting
  test depends on OTel's in-memory exporter and context propagation behaving
  under `pytest-asyncio`'s per-test event loops. If it proves flaky, the
  fallback is to assert on the `traceparent` field carried in the published
  envelope — weaker, but stable, and it still catches a detached-span regression
  because a detached span yields a different span id.
