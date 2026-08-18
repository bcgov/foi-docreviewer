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
- An offline Go fixture compile (`GOPROXY=off go test ./...`) cannot proceed
  because `integrationtests/go-consumer` lacks the required `go.sum` entry for
  `github.com/bcgov/foi-messaging-go v0.1.0`. No dependency download was
  attempted, per the no-network constraint.

Run the Redis/Go contract suite in its documented container environment after
the Go dependency checksum is available.
