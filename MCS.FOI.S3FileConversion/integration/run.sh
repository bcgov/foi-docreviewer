#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_dir="$(cd "$script_dir/.." && pwd)"
compose_file="${INTEGRATION_COMPOSE_FILE:-$repository_dir/docker-compose.integration.yml}"
run_id="${GITHUB_RUN_ID:-local}"
project_name="foi-conversion-e2e-${run_id}-$$"
results_dir="$repository_dir/TestResults/integration"
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
        printf 'Integration test failed; Compose diagnostics follow:\n' >&2
        cat "$results_dir/compose.log" >&2
    fi

    "${compose[@]}" down --volumes --remove-orphans
    exit "$original_status"
}
trap cleanup EXIT

cd "$repository_dir"
"${compose[@]}" up --build --abort-on-container-exit --exit-code-from integration-tests
