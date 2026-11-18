"""Execute the baseline preparation wrapper with captured archive/process peers."""

import io
import os
from pathlib import Path
import subprocess
import tarfile
import pytest


@pytest.mark.parametrize("encoding", ["utf-16", "utf-8"])
def test_baseline_requirements_support_legacy_and_upgraded_encoding(tmp_path, encoding):
    content = "Flask==2.1.2\n-e git+https://github.com/bcgov/sbc-common-components.git#egg=sbc-common-components&subdirectory=python\n"
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as bundle:
        for name, data in {
            "requirements.txt": content.encode(encoding),
            "dockerfile": b"FROM example\n",
            "reviewer_api/__init__.py": b"",
        }.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            bundle.addfile(info, io.BytesIO(data))
    binpath = tmp_path / "bin"
    binpath.mkdir()
    for name, script in {
        "git": '#!/bin/sh\ncat "$BASELINE_ARCHIVE"\n',
        "docker": "#!/bin/sh\nexit 0\n",
    }.items():
        executable = binpath / name
        executable.write_text(script)
        executable.chmod(0o755)
    source = tmp_path / "baseline"
    runner = Path(__file__).parents[1] / "scripts/prepare-upgrade-baseline.sh"
    result = subprocess.run(
        ["bash", str(runner), "captured-sha"],
        env=dict(
            os.environ,
            PATH=str(binpath) + ":" + os.environ["PATH"],
            BASELINE_ARCHIVE=str(archive),
            UPGRADE_BASELINE_SOURCE=str(source),
        ),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    rewritten = (source / "requirements.txt").read_text()
    assert "Flask==2.1.2" in rewritten
    assert (
        "sbc-common-components.git@67bb5e775370970aa7b674b1185d195a51fd7eeb#"
        in rewritten
    )
