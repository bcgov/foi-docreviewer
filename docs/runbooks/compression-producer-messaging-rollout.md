# Compression producer messaging rollout

This runbook moves Dedupe compression publishing from the legacy Walrus stream
format to the standard Watermill-compatible Redis Streams format. It covers the
normal topic `foi:compression` and the large-file topic
`foi:compression-large`.

The rollout is staged by environment and by deployment. A deployment has one
process-wide publishing mode: `legacy` or `standard`. Do not configure or
implement dual-publish during rollout or rollback.

## Preconditions

Before changing any Dedupe deployment:

- Confirm the consumer release understands the standard envelope and typed
  payload for `document.compression.requested`, schema `1.0.0`.
- Confirm the normal and large-file consumers use separate topics:
  `foi:compression` and `foi:compression-large`.
- Confirm the rollback-only legacy stream keys are provisioned for the affected
  deployment. Standard mode does not require those keys, but legacy mode does.
- Confirm the operator can inspect Redis stream, consumer-group, DLQ, and job
  state without printing payloads, credentials, or tokens.
- Record the rollout start time and the planned end of the rollback window.

For every `redis-cli` command below, authenticate through a protected process
environment rather than a command-line argument:

```bash
# Use a protected operator environment or an interactive secret prompt.
# Do not place the password in shell history or in process arguments.
export REDISCLI_AUTH="${REDIS_PASSWORD:?set this in the protected environment}"
```

Do not use `--pass`, paste the password into a command, or put it in a script,
shell history, ticket, or process argument list. Unset `REDISCLI_AUTH` when the
operator session ends. If the password is not already available in a protected
environment, use the approved interactive prompt/bootstrap procedure instead
of echoing or exporting it from command text.

The standard publisher emits exactly one `XADD` to the selected topic. A
successful publish has one Watermill UUID field, one serialized `payload`, and
empty `metadata`; it must not also write to the legacy stream.

## Staged rollout

Perform each stage only after the checks in the preceding stage are green.

### 1. Release all environments in legacy mode

Deploy the producer build to every environment with:

```text
COMPRESSION_MESSAGING_MODE=legacy
```

Keep existing `COMPRESSION_STREAM_KEY` values unchanged. Verify startup logs
show `mode=legacy` and the expected legacy stream, and verify normal
compression processing remains unchanged. This release establishes the
rollback-capable binary/configuration before any consumer is exposed to the
new topics.

The OpenShift Dedupe templates parameterize `COMPRESSION_MESSAGING_MODE`,
`MESSAGING_STREAM_PREFIX`, and `COMPRESSION_TOPIC`. Their rollout-safe defaults
are `legacy`, `foi`, and `compression` (normal) or `compression-large` (large
files); use the explicit standard values in the cutover stages below rather
than changing those defaults globally.

### 2. Deploy consumers with empty standard topics

Create or verify the standard streams and consumer groups are empty before
starting standard consumers. Redis creates a stream on first `XADD`, so an
empty check should normally return zero entries or a missing key:

```bash
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
  EXISTS foi:compression foi:compression-large
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
  XLEN foi:compression
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
  XLEN foi:compression-large
```

Deploy the compatible consumers while both topics are empty. Verify the
consumer groups are attached to the correct topic and that no pending or DLQ
entries exist before publishing standard events. `XINFO GROUPS` is valid only
after the consumer has created the stream and group; do not run it
unconditionally against a missing stream. Use this tolerant check after the
consumer deployment:

```bash
for stream in foi:compression foi:compression-large; do
  if [ "$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
      EXISTS "$stream")" = "1" ]; then
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
      XINFO GROUPS "$stream"
  else
    echo "$stream: missing (empty; consumer has not created it)"
  fi
done
```

Treat a missing stream as empty during this pre-publish check. Do not seed the
topics with legacy flat-field entries; they are not standard typed events.

### 3. Switch normal Dedupe

Change only the normal Dedupe deployment to:

```text
COMPRESSION_MESSAGING_MODE=standard
MESSAGING_STREAM_PREFIX=foi
COMPRESSION_TOPIC=compression
```

Restart or roll the normal Dedupe deployment using the normal deployment
procedure. Confirm startup reports `mode=standard` and
`stream=foi:compression`. Produce a controlled compression job and verify all
of the following before proceeding:

1. The event is consumed as a typed `document.compression.requested` event.
2. The consumer acknowledges it and the pending list returns to its baseline.
3. The stream has the expected new entry and no duplicate entry was written to
   the legacy stream.
4. Both DLQs remain at baseline and have no new entry for the controlled job.
5. The `CompressionJob` record reaches `version=3`. Its relevant fields are
   `compressionjobid`, `version`, `status`, and `message`; `status` is the
   terminal outcome field. In the approved job view, query by the compression
   `job ID` and inspect only its `version`, `status`, and terminal outcome. The
   approved job view/query must expose a sanitized terminal outcome derived
   from `message` (for example, an approved status/outcome field). Record only
   that approved outcome code; never inspect or record raw `message` text. If
   no sanitized outcome field exists, the compression service owner must use
   the approved `version=3` and `status` outcome as the authoritative check and
   must not inspect `message` directly. The existing CompressionJob service
   accepts completion (`status=completed`), error (`status=error`), or skipped
   (`status=skipped`) as version-3 terminal outcomes. Record only the job ID,
   version, status, and approved outcome, not message text or document fields.
6. The large-file topic remains unchanged and isolated.

Use the following bounded, metadata-only inspection commands. They never read
entries, so they cannot print event payload fields. Set `CONSUMER_GROUP` to the
group assigned to the deployment being checked.

```bash
for stream in foi:compression foi:compression-large; do
  if [ "$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
      EXISTS "$stream")" = "1" ]; then
    printf '%s entries: ' "$stream"
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
      XLEN "$stream"
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
      XINFO GROUPS "$stream"
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
      XPENDING "$stream" "$CONSUMER_GROUP"
  else
    echo "$stream: missing (empty; no group or pending state to inspect)"
  fi
done

for dlq in foi:compression.dlq foi:compression-large.dlq; do
  if [ "$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
      EXISTS "$dlq")" = "1" ]; then
    printf '%s entries: ' "$dlq"
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
      XLEN "$dlq"
  else
    echo "$dlq: missing (empty)"
  fi
done
```

Check the `CompressionJob` record by job ID in the approved operational view,
using `version`, `status`, and the sanitized terminal outcome only. If that
view has no sanitized outcome derived from `message`, use the approved
version/status outcome under the compression service owner's direction; never
open, print, or copy raw `message`. Do not dump the message, document, event
payload, S3 path, password, or user token into a terminal or ticket.

### 4. Switch large-file Dedupe

Only after the normal topic passes its verification window, change the
large-file deployment to:

```text
COMPRESSION_MESSAGING_MODE=standard
MESSAGING_STREAM_PREFIX=foi
COMPRESSION_TOPIC=compression-large
```

Roll the large-file deployment and verify startup reports
`stream=foi:compression-large`. Run a controlled large-file job and repeat the
typed-consumption, acknowledgment, pending-list, DLQ, version-3 outcome, and
legacy-no-duplicate checks. Confirm normal traffic continues on
`foi:compression` and does not appear on the large-file topic.

## Rollback

Rollback is deployment-specific. If normal or large-file verification fails,
pause new work for the affected deployment if the operational procedure
allows it, then perform every check below before restarting in legacy mode.

### Required checks before switching back

1. Identify the affected topic and its consumer group. Record the pending
   count and pending-ID range from the `XPENDING` summary, plus the group
   metadata from `XINFO GROUPS`; neither command reads stream entries or prints
   payload fields. Do not acknowledge, delete, or replay entries as part of an
   emergency inspection.

   ```bash
   for stream in foi:compression foi:compression-large; do
     if [ "$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
         EXISTS "$stream")" = "1" ]; then
       redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
         XINFO GROUPS "$stream"
       redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
         XPENDING "$stream" "$CONSUMER_GROUP"
     else
       echo "$stream: missing (empty; no group or pending range to inspect)"
     fi
   done
   ```

2. Inspect both DLQ conventions used by the consumer fixture and service,
   `foi:compression.dlq` and `foi:compression-large.dlq`. Capture counts and
   IDs only; never copy payload fields into the incident record:

   ```bash
   redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
     XLEN foi:compression.dlq
   redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" --user "$REDIS_USER" \
     XLEN foi:compression-large.dlq
   ```

3. Check each controlled or in-flight `CompressionJob` by job ID in the
   approved job view. Record only `version`, `status`, and terminal outcome;
   do not copy its message, filename, path, or payload into the incident
   record.
4. Confirm the legacy stream key exists and that the legacy consumer path is
   healthy before stopping the standard producer.
5. The compression service owner/on-call is the decision owner. Before any
   restart, obtain a bounded incident decision from that owner naming the
   affected deployment, topic, pending-entry treatment, job IDs in scope, and
   the rollback/forward action. Pending standard entries remain available for
   owner-directed idempotent handling and forensics; they are never blindly
   republished into the legacy stream.

After those checks, restart only the affected deployment with its pre-provisioned
legacy configuration:

```text
COMPRESSION_MESSAGING_MODE=legacy
COMPRESSION_STREAM_KEY=<affected legacy stream key>
```

Verify startup reports `mode=legacy`, then verify new legacy traffic, job
state, pending age, and DLQ state. Keep the standard topic available for
forensic inspection until the rollback window closes.

There is no dual-publish rollback. Never leave standard and legacy publishers
enabled together, and never copy a standard event into the legacy stream just
to make counts appear equal. Resolve already-pending standard events only by
the compression service owner/on-call's bounded decision and the consumer's
idempotent handling/forensic procedure; those procedures are not added by this
task.

## Safe observability

Allowed log and dashboard fields are operational identifiers and outcomes:

- publishing mode and logical stream name;
- Redis stream ID and event ID, when the publisher returns them;
- correlation ID;
- compression job ID and document master ID;
- publish/consume/acknowledge outcome;
- pending count, oldest pending age, and DLQ count/IDs;
- count and age of stale version-1-only jobs.

Document master IDs are allowed only as approved operational identifiers in
restricted logs or approved operational views. Never combine a document master
ID with a payload, document path, filename, or document contents in the same
log or incident record. Do not log or export event payloads, document contents,
document paths, passwords, Redis credentials, access tokens, user tokens, or
full message objects. When inspecting Redis, use `XINFO`, `XINFO GROUPS`,
`XLEN`, and `XPENDING` for counts, IDs, and ages. If `XRANGE`/`XREAD` is
required for a narrowly scoped incident, inspect only metadata fields in a
secured operator session and redact the payload before recording results.

Operational checks during the rollback window should alert on:

- pending age increasing beyond the consumer's agreed threshold;
- any new DLQ entry or a DLQ count that does not return to baseline;
- a standard event published to the wrong topic;
- a version-1-only job that remains stale after the normal processing SLA;
- a stream or consumer group receiving traffic from both normal and large-file
  deployments unexpectedly.

## Legacy retirement gate

Legacy mode remains available until the documented rollback window is closed
and the service owner signs off on the operational evidence. Remove legacy mode
only when all of these are true:

- normal and large-file standard topics have remained healthy for the full
  rollback window;
- no legacy consumer-group pending entries remain and legacy streams are
  drained according to the retention decision;
- no unresolved DLQ or stale version-1-only job remains attributable to the
  migration;
- the legacy formatter and Walrus compression publishing path have been
  removed in a later, separately reviewed change;
- obsolete `COMPRESSION_STREAM_KEY` configuration and related secret entries
  have been deleted in that later change.

This task does not remove the legacy formatter, Walrus path, configuration,
transactional outbox, reconciliation, trace propagation, unrelated publishers,
or a production Go handler. Those items remain explicitly deferred.
