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
"${compose[@]}" up --build --abort-on-container-exit --exit-code-from e2e-tests "$@"
