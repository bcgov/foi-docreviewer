#!/usr/bin/env bash
set -euo pipefail
service_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
phase=${1:-candidate}
if [[ "$#" -gt 0 ]]; then shift; fi
case "$phase" in baseline|candidate) ;; *) echo 'Expected baseline or candidate' >&2; exit 2 ;; esac
run_id=${UPGRADE_RUN_ID:-$$}
export UPGRADE_PHASE="$phase"
export UPGRADE_UID=${UPGRADE_UID:-$(id -u)} UPGRADE_GID=${UPGRADE_GID:-$(id -g)}
export UPGRADE_EVIDENCE_DIR=${UPGRADE_EVIDENCE_DIR:-/tmp/reviewer-api-python-upgrade/$phase}
export UPGRADE_TLS_DIR=${UPGRADE_TLS_DIR:-/tmp/reviewer-api-python-upgrade/tls/$phase-$run_id}
export UPGRADE_APP_IMAGE=${UPGRADE_BASELINE_IMAGE:-foi-reviewer-api-upgrade:baseline}
export UPGRADE_SOURCE_DIR=${UPGRADE_BASELINE_SOURCE:-/tmp/reviewer-api-python-upgrade/baseline-source}
if [[ "$phase" = candidate ]]; then
    export UPGRADE_APP_IMAGE=foi-reviewer-api-upgrade:candidate
    export UPGRADE_SOURCE_DIR="$service_dir"
    docker build -f "$service_dir/dockerfile" -t "$UPGRADE_APP_IMAGE" "$service_dir"
else
    docker image inspect "$UPGRADE_APP_IMAGE" >/dev/null
    [[ -f "$UPGRADE_SOURCE_DIR/reviewer_api/__init__.py" ]] || { echo "Baseline source missing: $UPGRADE_SOURCE_DIR" >&2; exit 1; }
fi
mkdir -p "$UPGRADE_EVIDENCE_DIR" "$UPGRADE_TLS_DIR"
docker image inspect --format '{{.Id}}' "$UPGRADE_APP_IMAGE" > "$UPGRADE_EVIDENCE_DIR/image-id.txt"
openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj /CN=storage -addext subjectAltName=DNS:storage -keyout "$UPGRADE_TLS_DIR/storage.key" -out "$UPGRADE_TLS_DIR/storage.crt" > "$UPGRADE_EVIDENCE_DIR/tls.log" 2>&1
# SeaweedFS drops to its own uid 1000. openssl writes the key 0600 for the invoking
# user, so on hosts where that is not uid 1000 (GitHub runners use 1001) the HTTPS
# listener cannot read it and silently never answers. The key is disposable and
# per-run, so make it readable to the storage container.
chmod 0644 "$UPGRADE_TLS_DIR/storage.key"
project="reviewer-upgrade-${phase}-${run_id}"
printf '%s\n' "$project" > "$UPGRADE_EVIDENCE_DIR/compose-project.txt"
compose=(docker compose --project-name "$project" --env-file "$service_dir/tests/upgrade.env" -f "$service_dir/tests/compose.python-upgrade.yml")
cleanup() { "${compose[@]}" logs --no-color > "$UPGRADE_EVIDENCE_DIR/peers.log" 2>&1; "${compose[@]}" down --remove-orphans; }
trap cleanup EXIT
"${compose[@]}" build checks
"${compose[@]}" up -d --wait --wait-timeout 90 postgres redis storage fixtures
if [[ "$phase" = candidate ]]; then
    bash "$service_dir/scripts/check-migration-parity.sh" "$project" "$UPGRADE_EVIDENCE_DIR"
fi
"${compose[@]}" run --rm -e UPGRADE_PHASE="$phase" checks "$@" 2>&1 | tee "$UPGRADE_EVIDENCE_DIR/checks.log"
