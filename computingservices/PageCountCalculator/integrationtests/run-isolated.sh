#!/usr/bin/env bash
# A private network, Redis and two disposable databases. No host service ports.
set -euo pipefail
image=${1:?Usage: run-isolated.sh TEST_IMAGE}
shift
service=$(cd "$(dirname "$0")/.." && pwd)
token="pagecount-it-$(date +%s)-$$"
cleanup() {
  docker rm -f "$token-redis" "$token-db" >/dev/null 2>&1 || true
  docker network rm "$token" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create "$token" >/dev/null
docker run -d --name "$token-redis" --network "$token" --network-alias redis \
  redis:7-alpine redis-server --requirepass synthetic-only >/dev/null
docker run -d --name "$token-db" --network "$token" --network-alias db \
  -e POSTGRES_PASSWORD=synthetic-only postgres:16-alpine >/dev/null
for attempt in $(seq 1 60); do
  if docker exec "$token-db" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1 && \
     docker exec -e REDISCLI_AUTH=synthetic-only "$token-redis" redis-cli ping >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" = 60 ]]; then
    echo 'Disposable infrastructure readiness timed out' >&2
    exit 1
  fi
  sleep 1
done
for database in pagecount_documents_it_disposable pagecount_foi_it_disposable; do
  docker exec "$token-db" createdb -U postgres "$database"
  docker exec "$token-db" psql -U postgres -d "$database" -v ON_ERROR_STOP=1 -c \
    "CREATE TABLE pagecount_it_owner (token text); INSERT INTO pagecount_it_owner VALUES ('$token')" >/dev/null
done
docker exec "$token-db" psql -U postgres -v ON_ERROR_STOP=1 -c \
  "CREATE ROLE pagecount_doc LOGIN PASSWORD 'synthetic-only'; CREATE ROLE pagecount_foi LOGIN PASSWORD 'synthetic-only'" >/dev/null
docker exec -e REDISCLI_AUTH=synthetic-only "$token-redis" redis-cli \
  SET pagecount_it_owner "$token" >/dev/null
docker run --rm --network "$token" --entrypoint sh \
  -v "$service/integrationtests:/tests:ro" \
  -e RUN_PAGECOUNT_INTEGRATION=1 -e PAGECOUNT_TEST_INSTANCE="$token" \
  -e REDIS_HOST=redis -e REDIS_PORT=6379 -e REDIS_PASSWORD=synthetic-only \
  -e DOCUMENTSERVICE_DB_HOST=db -e DOCUMENTSERVICE_DB_PORT=5432 \
  -e DOCUMENTSERVICE_DB_NAME=pagecount_documents_it_disposable \
  -e DOCUMENTSERVICE_DB_USER=postgres -e DOCUMENTSERVICE_DB_PASSWORD=synthetic-only \
  -e FOI_DB_HOST=db -e FOI_DB_PORT=5432 -e FOI_DB_NAME=pagecount_foi_it_disposable \
  -e FOI_DB_USER=postgres -e FOI_DB_PASSWORD=synthetic-only \
  "$image" -ec '
    python -m pytest -q -s -p no:cacheprovider --junitxml=/tmp/integration.xml \
      /tests/test_pagecount_pipeline.py "$@"
    python /tests/check-results.py /tmp/integration.xml
  ' sh "$@"
