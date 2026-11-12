#!/usr/bin/env bash
# Regression check: the pipeline must execute the packaged application even
# when the checkout supplying its test harness has an unusable entrypoint.
set -euo pipefail
image=${1:?Usage: verify-packaged-worker.sh TEST_IMAGE}
shift
service=$(cd "$(dirname "$0")/.." && pwd)
scratch=$(mktemp -d /tmp/pdfstitch-packaged.XXXXXX)
trap 'rm -rf "$scratch"' EXIT
mkdir "$scratch/integrationtests"
cp "$service/integrationtests/run-isolated.sh" "$service/integrationtests/test_pdfstitch_pipeline.py" "$scratch/integrationtests/"
printf '#!/bin/sh\nexit 97\n' > "$scratch/entrypoint.sh"
bash "$scratch/integrationtests/run-isolated.sh" "$image" "$@"
