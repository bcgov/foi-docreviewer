#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose_file="${E2E_COMPOSE_FILE:-$script_dir/docker-compose.e2e.yml}"
run_id="${GITHUB_RUN_ID:-local}"
project_name="foi-pipeline-e2e-${run_id}-$$"
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
        printf 'Pipeline e2e test failed; Compose diagnostics follow:\n' >&2
        cat "$results_dir/compose.log" >&2
    fi

    "${compose[@]}" down --volumes --remove-orphans
    exit "$original_status"
}
trap cleanup EXIT

cd "$script_dir"
# Bring up every dependency detached, then run the test container in the
# foreground and propagate its exit code. `up --abort-on-container-exit` was
# tried first, but that flag aborts the whole stack as soon as ANY container
# exits -- including the one-shot `db-migrate` container, which is *supposed*
# to exit 0 once it finishes -- which raced with e2e-tests startup and tore
# the stack down mid-run. `up -d --build` (with no service filter) has its own
# trap: it also starts `e2e-tests` itself, so a second, concurrent test run
# was racing the one from the explicit `run` below. Listing the dependency
# services explicitly avoids both problems.
"${compose[@]}" up -d --build postgres db-migrate redis seaweedfs record-formats activemq "$@"
"${compose[@]}" run --rm --build e2e-tests
