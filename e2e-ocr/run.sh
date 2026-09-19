#!/usr/bin/env bash
# Same shape as e2e/run.sh: isolated project name, log capture, teardown.
set -Eeuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose_file="${E2E_OCR_COMPOSE_FILE:-$script_dir/docker-compose.ocr.yml}"
run_id="${GITHUB_RUN_ID:-local}"
project_name="foi-ocr-e2e-${run_id}-$$"
results_dir="$script_dir/TestResults"
mkdir -p "$results_dir"

compose=(docker compose --project-name "$project_name" --file "$compose_file")

cleanup() {
    local original_status=$?
    trap - EXIT
    set +e
    {
        "${compose[@]}" ps
        "${compose[@]}" logs --no-color
    } >"$results_dir/compose.log" 2>&1
    if (( original_status != 0 )); then
        printf 'OCR e2e test failed; Compose diagnostics follow:\n' >&2
        cat "$results_dir/compose.log" >&2
    fi
    "${compose[@]}" down --volumes --remove-orphans
    exit "$original_status"
}
trap cleanup EXIT

cd "$script_dir"
# `run` starts e2e-tests' depends_on graph (honouring service_healthy /
# service_completed_successfully) without `up --abort-on-container-exit`
# tearing the stack down when the one-shot db-migrate exits 0.
"${compose[@]}" run --rm --build e2e-tests "$@" 2>&1 | tee "$results_dir/e2e-tests.log"
