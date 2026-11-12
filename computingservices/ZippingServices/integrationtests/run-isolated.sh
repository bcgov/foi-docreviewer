#!/usr/bin/env bash
# Own network, empty database, Redis instance and TLS S3 store; no shared state.
set -euo pipefail
image=${1:?Usage: run-isolated.sh TEST_IMAGE}
shift
service=$(cd "$(dirname "$0")/.." && pwd)
token="zipper-it-$(date +%s)-$$"
scratch=$(mktemp -d /tmp/zipper-it.XXXXXX)
cleanup() {
  docker rm -f "$token-redis" "$token-db" "$token-s3" >/dev/null 2>&1 || true
  docker network rm "$token" >/dev/null 2>&1 || true
  # Only files created in this invocation's mktemp directory.
  rm -rf "$scratch"
}
trap cleanup EXIT
mkdir "$scratch/certs"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=s3 \
  -addext subjectAltName=DNS:s3 -keyout "$scratch/certs/private.key" \
  -out "$scratch/certs/public.crt" >/dev/null 2>&1
chmod 755 "$scratch" "$scratch/certs"
chmod 644 "$scratch/certs/public.crt"
docker network create "$token" >/dev/null
docker run -d --name "$token-redis" --network "$token" --network-alias redis \
  redis:7-alpine >/dev/null
docker run -d --name "$token-db" --network "$token" --network-alias db \
  -e POSTGRES_PASSWORD=synthetic-only -e POSTGRES_DB=zipper_it_disposable \
  postgres:16-alpine >/dev/null
cat > "$scratch/s3.json" <<'JSON'
{"identities":[{"name":"synthetic","credentials":[{"accessKey":"synthetic-access","secretKey":"synthetic-secret-only"}],"actions":["Admin","Read","List","Tagging","Write"]}]}
JSON
docker run -d --name "$token-s3" --network "$token" --network-alias s3 \
  -v "$scratch/certs:/certs:ro" -v "$scratch/s3.json:/etc/s3.json:ro" \
  chrislusf/seaweedfs:4.46 server -dir=/data -s3 -s3.port.https=9000 \
  -s3.cert.file=/certs/public.crt -s3.key.file=/certs/private.key -s3.config=/etc/s3.json \
  -master.volumeSizeLimitMB=100 -volume.max=2 >/dev/null
for attempt in $(seq 1 60); do
  if docker exec "$token-redis" redis-cli ping >/dev/null 2>&1 && \
     docker exec "$token-db" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1 && \
     docker exec "$token-s3" sh -c 'wget -q -O /dev/null http://127.0.0.1:9333/cluster/status && nc -z 127.0.0.1 9000' >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" = 60 ]; then
    echo 'Disposable infrastructure readiness timed out' >&2
    exit 1
  fi
  sleep 1
done
docker exec "$token-db" psql -U postgres -d zipper_it_disposable -v ON_ERROR_STOP=1 -c \
  "CREATE TABLE zipper_it_owner (token text); INSERT INTO zipper_it_owner VALUES ('$token')" >/dev/null
docker exec "$token-redis" redis-cli SET zipper_it_owner "$token" >/dev/null
docker run --rm --memory=512m --cpus=2 --network "$token" --entrypoint sh \
  -v "$service/integrationtests:/tests:ro" -v "$scratch/certs/public.crt:/tmp/s3-ca.crt:ro" \
  -e RUN_ZIPPER_INTEGRATION=1 \
  -e ZIPPER_TEST_INSTANCE="$token" \
  -e REDIS_HOST=redis -e REDIS_PORT=6379 -e REDIS_PASSWORD= \
  -e NOTIFICATION_REDIS_HOST=redis -e NOTIFICATION_REDIS_PORT=6379 -e NOTIFICATION_REDIS_PASSWORD= \
  -e DB_HOST=db -e DB_PORT=5432 -e DB_NAME=zipper_it_disposable \
  -e DB_USER=postgres -e DB_PASSWORD=synthetic-only \
  -e S3_HOST=s3:9000 -e S3_REGION=us-east-1 -e S3_SERVICE=s3 -e S3_ENV=it \
  -e AWS_ACCESS_KEY_ID=synthetic-access -e AWS_SECRET_ACCESS_KEY=synthetic-secret-only \
  -e REQUESTS_CA_BUNDLE=/tmp/s3-ca.crt \
  "$image" -ec '
    python -m pytest -q -s -p no:cacheprovider --junitxml=/tmp/integration.xml /tests/test_zipper_pipeline.py "$@"
    python /tests/check-results.py /tmp/integration.xml
  ' sh "$@"
