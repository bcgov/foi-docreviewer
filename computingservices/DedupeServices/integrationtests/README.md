# Compression producer compatibility fixture

This opt-in integration suite validates that the Python
`StandardCompressionPublisher` can be consumed by the public Go messaging
contract. It does not exercise or modify a production Go service.

The fixture starts Redis `7.0-alpine` on `127.0.0.1:16379`, publishes to both
`foi:compression` and `foi:compression-large`, and runs a test-only typed Go
consumer. The consumer is pinned to `github.com/bcgov/foi-messaging-go v0.1.0`.
That dependency declares Go `1.25.0`; use a Go 1.25 toolchain (or Go's
configured automatic toolchain selection).

Run the suite separately from the fast unit tests:

```bash
cd computingservices/DedupeServices
RUN_COMPRESSION_CONTRACT_TESTS=1 pytest -q integrationtests/test_go_compression_contract.py
```

The test manages the Redis container and removes its volume on teardown. To
inspect the Redis 7 fixture manually from this directory instead:

```bash
cd computingservices/DedupeServices/integrationtests
docker compose -p foimod5199compressioncontract -f docker-compose.yml up -d --wait
docker compose -p foimod5199compressioncontract -f docker-compose.yml down --volumes
```

The suite requires Docker access, a free host port `16379`, Python test
dependencies from `computingservices/DedupeServices/requirements.txt`, and the
pinned Go dependency (including its transitive modules) available to the Go
toolchain.
