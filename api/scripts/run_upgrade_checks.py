"""Bootstrap isolated tests before any Reviewer imports."""

import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from check_test_environment import validate_test_environment

if sys.argv[1:] == ["--guard-only"]:
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "pytest",
                "--noconftest",
                str(Path(__file__).parents[1] / "tests/test_test_environment.py"),
                "-q",
            ]
        )
    )
validate_test_environment(os.environ)
sys.path.insert(0, "/verification-source")
import pytest

evidence = Path("/evidence")
evidence.mkdir(exist_ok=True)
(evidence / "runtime.json").write_text(
    json.dumps(
        {
            "python": platform.python_version(),
            "packages": {
                d.metadata["Name"]: d.version for d in metadata.distributions()
            },
        },
        indent=2,
    )
)
with (evidence / "pip-check.txt").open("w") as output:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "check"], stdout=output, stderr=subprocess.STDOUT
    )
# Baseline inconsistencies are evidence, not grounds to skip its behavioral tests.
if result.returncode and os.environ.get("UPGRADE_PHASE") != "baseline":
    raise SystemExit(result.returncode)
args = sys.argv[1:] or ["/verification-source/tests", "--continue-on-collection-errors"]
args = [
    (
        a.replace("tests/", "/verification-source/tests/", 1)
        if a.startswith("tests/")
        else a
    )
    for a in args
]
if args and args[0].startswith("@"):
    args = [
        line.strip().replace("tests/", "/verification-source/tests/", 1)
        for line in Path("/verification-source/tests/python-upgrade-focused.txt")
        .read_text()
        .splitlines()
        if line.strip() and not line.startswith("#")
    ]
raise SystemExit(
    pytest.main(
        [*args, "-q", "-p", "no:cacheprovider", "--junitxml=/evidence/tests.xml"]
    )
)
