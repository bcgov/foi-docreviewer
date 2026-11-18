#!/usr/bin/env bash
set -euo pipefail
source_ref=${1:?Supply the pre-upgrade source SHA}
baseline_image=${UPGRADE_BASELINE_IMAGE:-foi-reviewer-api-upgrade:baseline}
source_dir=${UPGRADE_BASELINE_SOURCE:-/tmp/reviewer-api-python-upgrade/baseline-source}
if [[ -e "$source_dir/reviewer_api" ]]; then
    echo "Refusing to overwrite captured baseline source: $source_dir" >&2; exit 2
fi
mkdir -p "$source_dir"
git archive "$source_ref:api" | tar -x -C "$source_dir"
python3 - "$source_dir" <<'PYTHON'
from pathlib import Path
import sys
root=Path(sys.argv[1]); requirements=root/"requirements.txt"
data=requirements.read_bytes()
content=data.decode("utf-16" if data.startswith((b"\xff\xfe",b"\xfe\xff")) else "utf-8")
content=content.replace("sbc-common-components.git#", "sbc-common-components.git@67bb5e775370970aa7b674b1185d195a51fd7eeb#")
requirements.write_text(content)
(root/".dockerignore").write_text(".env\n.env.*\n**/.env\n**/.env.*\n")
(root/"scripts").mkdir(exist_ok=True)
PYTHON
docker build -f "$source_dir/dockerfile" -t "$baseline_image" "$source_dir"
docker image inspect --format '{{.Id}}' "$baseline_image" > "$source_dir/image-id.txt"
printf '%s\n' "$source_ref" > "$source_dir/source-sha.txt"
echo 'Reconstructed source-declared baseline; not a deployed artifact or the recorded local dependency layers.'
