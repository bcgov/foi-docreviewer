#!/usr/bin/env bash
set -euo pipefail
project=${1:?Compose project required}
evidence=${2:?Evidence directory required}
service_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
baseline=${UPGRADE_BASELINE_IMAGE:-foi-reviewer-api-upgrade:baseline}
compose=(docker compose --project-name "$project" --env-file "$service_dir/tests/upgrade.env" -f "$service_dir/tests/compose.python-upgrade.yml")
docker image inspect "$baseline" >/dev/null
# These commands only join the internal, disposable verification network.
docker run --rm --network "${project}_verification" --env-file "$service_dir/tests/upgrade.env" --entrypoint python "$baseline" manage.py db upgrade > "$evidence/baseline-migration.log" 2>&1
"${compose[@]}" exec -T postgres pg_dump -U postgres -d reviewer_upgrade_test --schema-only --no-owner --no-privileges | sed '/^\\restrict /d; /^\\unrestrict /d' > "$evidence/schema-before.sql"
"${compose[@]}" exec -T postgres psql -U postgres -d reviewer_upgrade_test -Atc 'select version_num from alembic_version order by version_num' > "$evidence/heads-before.txt"
docker run --rm --network "${project}_verification" --env-file "$service_dir/tests/upgrade.env" --entrypoint python foi-reviewer-api-upgrade:candidate manage.py db upgrade > "$evidence/candidate-migration.log" 2>&1
"${compose[@]}" exec -T postgres pg_dump -U postgres -d reviewer_upgrade_test --schema-only --no-owner --no-privileges | sed '/^\\restrict /d; /^\\unrestrict /d' > "$evidence/schema-after.sql"
"${compose[@]}" exec -T postgres psql -U postgres -d reviewer_upgrade_test -Atc 'select version_num from alembic_version order by version_num' > "$evidence/heads-after.txt"
diff -u "$evidence/schema-before.sql" "$evidence/schema-after.sql" > "$evidence/schema.diff"
diff -u "$evidence/heads-before.txt" "$evidence/heads-after.txt" > "$evidence/heads.diff"
echo 'Baseline-to-candidate migration schema and heads match.'

# Candidate writes survive an old-image read without schema reversal or replay.
docker run --rm --network "${project}_verification" --env-file "$service_dir/tests/upgrade.env" -v "$service_dir/scripts/rehearse_upgrade_rollback.py:/rollback.py:ro" -e PYTHONPATH=/app --entrypoint python foi-reviewer-api-upgrade:candidate /rollback.py write > "$evidence/rollback-write.log" 2>&1
docker run --rm --network "${project}_verification" --env-file "$service_dir/tests/upgrade.env" -v "$service_dir/scripts/rehearse_upgrade_rollback.py:/rollback.py:ro" -e PYTHONPATH=/app --entrypoint python "$baseline" /rollback.py read > "$evidence/rollback-read.log" 2>&1
