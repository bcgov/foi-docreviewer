# Contributing

This is a template repository: contributions here should improve the
reference itself (patterns, docs, fixes), not add product features specific
to any one service. If you've forked this to build a real service, these
conventions are a reasonable starting point but yours to change.

## Getting set up

```bash
poetry install       # install dependencies
make up              # docker compose up --build -d; starts Redis and the worker
make demo URL=<pdf>  # publish one request twice; watch it process exactly once
```

See [README.md](README.md) for the full quickstart and
[CLAUDE.md](CLAUDE.md) for the architecture reference.

## Before you open a PR

```bash
make fmt        # poetry run black . && poetry run ruff check --fix .
make lint       # poetry run ruff check .
make test       # unit tests, no Docker required
make test-all   # full suite, including testcontainers integration tests
```

`make test-all` is required, not optional, before opening a PR — see
["Why testing locally with Docker matters"](BEST_PRACTICES.md#4-testing-strategy-unit-vs-integration)
in `BEST_PRACTICES.md`. The unit suite never touches Redis; only the full
suite (or `make up && make demo`) proves the change works against the real
dependency.

## Code style

- Formatting: [Black](https://black.readthedocs.io/), line length 88.
- Linting: [Ruff](https://docs.astral.sh/ruff/), selecting `E`, `F`, `W`,
  `B`, `I` (with `E501` ignored — Black already enforces line length).
- Import order: standard library, then third-party, then local — Ruff's `I`
  rule enforces this; `make fmt` fixes it automatically.
- No comments explaining *what* code does — names should already make that
  clear. A comment is only worth adding for a non-obvious *why* (a hidden
  constraint, a workaround, something that would surprise a reader). The
  handlers here are the exception: they carry long docstrings because the
  *why* (idempotency ordering, failure windows) is the point of the template.
- `core/*` modules use `from __future__ import annotations`.

## Adding a new event type

1. Add the payload model under `messaging/models/events/`.
2. Add the event type to the `Literal` and to the `EventPayload` union in
   `messaging/models/envelope.py`.
3. Write a handler under `messaging/consumer/handlers/`.
4. Register the handler in `HANDLERS` in
   `messaging/consumer/dispatcher.py`.

`pdf_preprocessing_requested.py` is a worked example of the handler shape;
follow it. Two rules a new handler must respect:

- **Handlers must be idempotent.** Redis Streams delivery is at-least-once,
  and redelivery is expected, not a bug. Guard with a conditional write (the
  PDF handler uses `HSETNX preprocessing:<job_id>`), and put the early return
  *before* any publish — otherwise one redelivery amplifies into a duplicate
  downstream event.
- **Never publish upstream from a handler.** A handler that republishes what
  it consumes onto the same stream is an infinite loop that looks like a busy
  worker. This service keeps input (`STREAM_NAME`) and output
  (`OUTPUT_STREAM_NAME`) on separate streams.

## Handler state

Handlers that need state take their own Redis client from
`messaging/state.py` (`get_state_client()`), never the consumer's — there is
no request scope here to inherit a connection from, and a handler must not
issue commands on the connection the read loop depends on. Anything a handler
writes should carry a TTL (`STATE_TTL_SECONDS`); this template's state keys
are demo scaffolding, not a durable store.

## Tracing

If you touch the producer or the consumer's message loop, keep the context
chain intact: the producer injects ambient trace context into
`EventEnvelope.traceparent`, and the consumer must make its message span
**current** with `start_as_current_span`, not hold it detached. A detached
span looks identical in logs and exports, and silently orphans every event a
handler publishes. `tests/integration/test_tracing.py` asserts on parent span
ids precisely to catch that.

## Testing expectations

- New logic in `messaging/`, `health/`, `core/`, or the worker's lifecycle
  needs a unit test in `tests/unit/` — these run without Docker.
- A change to the consumer's failure handling, handler behavior, trace
  propagation, or the CLI needs an integration test in `tests/integration/`
  (real Redis via testcontainers).
- Don't rely on the unit suite alone to validate a change that touches Redis
  or tracing — see `make test-all` above.

## Commit messages

Keep commits scoped to one logical change, and write the message around the
*why*, not a restatement of the diff. Match the existing history's style
(`git log --oneline`), e.g. `fix: ...`, `docs: ...`, `test: ...`,
`style: ...`.

## Documentation

If a change affects a documented behavior or pattern, update the relevant
doc in the same PR:

- `README.md` — quickstart, demo flow, "make it yours" checklist.
- `CLAUDE.md` — architecture reference used for AI-assisted development.
- `BEST_PRACTICES.md` — the practices behind the structure, and why they
  exist.
