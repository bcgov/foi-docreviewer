# FOIMOD-5199 Compression Producer Messaging Final Remediation

## Status

Implemented the final whole-branch remediation findings without adding a
production Go consumer, transactional outbox, or application retry loop.

## Remediations

- Parameterized `COMPRESSION_MESSAGING_MODE`, `MESSAGING_STREAM_PREFIX`, and
  `COMPRESSION_TOPIC` in both Dedupe OpenShift templates. Both deployments now
  default to `legacy`; normal and large-file topics remain separately
  configurable as `compression` and `compression-large`.
- Changed `sample.env` to use the rollout-safe `legacy` mode and retained local
  topic/prefix settings. The rollout runbook retains explicit `standard`
  cutover values and now explains the template defaults.
- Made `compressionproducermessage` decode native booleans and Redis string
  booleans (`true`/`false`, case-insensitive), rejecting all other values with
  `ValueError`.
- Validated the complete `CompressionProducerMessage` payload shape before
  standard publication, including required field presence, exact contract
  types, optional field types, and v0.1.0 event type/schema/source constants.
  Values are validated, never coerced or normalized.
- Added the Redis stream ID to safe compression publication logs.
- Updated the Redis/Go contract test to build its payload using the Python
  model's `to_dict()` and expanded its Go fixture types/assertions to cover the
  realistic payload fields used by the test.
- Added repository-local `pytest.ini` discovery for the existing
  `testcompression*.py` convention.

## Verification

Passed:

```text
cd computingservices/DedupeServices
pytest -q unittests/testcompressionproducermessage.py \
  unittests/testcompressionevents.py \
  unittests/testcompressionproducerservice.py \
  unittests/testdeploymentconfiguration.py \
  integrationtests/test_go_compression_contract.py
# 48 passed, 3 skipped

python -m compileall -q models/compressionproducermessage.py \
  rstreamio/compressionevents.py \
  services/compressionproducerservice.py \
  integrationtests/test_go_compression_contract.py

git diff --check
```

The focused Go/Redis integration tests intentionally skip unless
`RUN_COMPRESSION_CONTRACT_TESTS=1` is set.

## Remaining Environment Concerns

- `pytest unittests -q` now discovers the existing Dedupe naming convention,
  but full collection cannot run in this environment because unrelated legacy
  test modules import `pypdf`, which is not installed. The observed collection
  errors are `unittests/testcontext.py` and `unittests/testdedupedbservice.py`.
- The Go fixture now records the exact v0.1.0 module checksums in `go.sum`.
  Offline compilation still cannot proceed because transitive checksums for
  `github.com/redis/go-redis/v9`, Watermill, `github.com/google/uuid`, and
  OpenTelemetry are not present. The attempted escalated download was stopped
  at the user's direction, so no further dependency fetch was attempted.

Run the Redis/Go contract suite in its documented container environment after
the Go dependency checksum is available.

## Final Cleanup Update (2026-08-18)

- Corrected the Redis/Go contract assertion to expect
  `attributes.isattachment=true`, matching the typed Go fixture's JSON report.
  The live test remains intentionally skipped unless
  `RUN_COMPRESSION_CONTRACT_TESTS=1`; it is not claimed as passed here.
- Added `integrationtests/go-consumer/go.sum` with the exact
  `github.com/bcgov/foi-messaging-go v0.1.0` module and go.mod checksums.
- Replaced the normal-cutover `XINFO STREAM` inspection with a bounded script
  using only `EXISTS`, `XLEN`, `XINFO GROUPS`, and `XPENDING`. It retains
  missing-stream guards for both standard topics and both DLQs and never reads
  entry payload fields.
- Added `docs/foimod-5199-compression-messaging-migration-plan.md` as the
  concise producer addendum, linking the plan/runbook and recording rollout,
  rollback, topic isolation, legacy-window, verification, and deferred work.

Final checks:

```text
pytest unittests -q
# blocked during collection: pypdf is not installed for testcontext.py and
# testdedupedbservice.py

pytest -q unittests/testcompressionproducermessage.py \
  unittests/testcompressionevents.py \
  unittests/testcompressionproducerservice.py \
  unittests/testdeploymentconfiguration.py \
  integrationtests/test_go_compression_contract.py
# 48 passed, 3 skipped

GOPROXY=off GOCACHE=/tmp/foimod-5199-go-build go test ./...
# blocked by the missing transitive checksums listed above
```

## Final Fix Round Update

- Removed `optional: true` from the normal and large-file Dedupe compression
  secret references. Because OpenShift now defaults the mode to `legacy`, a
  missing `COMPRESSION_STREAM_KEY` or `COMPRESSION_STREAM_KEY_LARGEFILES`
  prevents the pod from starting with an unusable legacy configuration.
- Added pre-`XADD` validation for caller-supplied correlation IDs. A supplied
  value must be a non-blank string; invalid values raise `ValueError` without
  publishing.
- Replaced the rollback instruction to record a raw stream-ID range with a
  payload-safe `XINFO GROUPS` and `XPENDING` summary procedure. It records
  group metadata and pending count/ID range for both standard topics without
  reading entries.

Final checks:

```text
pytest unittests -q
# blocked during collection: pypdf is not installed for testcontext.py and
# testdedupedbservice.py

pytest -q unittests/testcompressionproducermessage.py \
  unittests/testcompressionevents.py \
  unittests/testcompressionproducerservice.py \
  unittests/testdeploymentconfiguration.py \
  integrationtests/test_go_compression_contract.py
# 52 passed, 3 skipped

python -m compileall -q models/compressionproducermessage.py \
  rstreamio/compressionevents.py \
  services/compressionproducerservice.py \
  integrationtests/test_go_compression_contract.py

gofmt -d integrationtests/go-consumer/main.go
git diff --check
```
