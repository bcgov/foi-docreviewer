"""Comparison must fail closed when a previously passing test disappears."""

from pathlib import Path
import subprocess
import sys
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/compare-upgrade-results.py"


@pytest.mark.parametrize(
    "candidate,code",
    [
        ("<testcase classname='suite' name='ok'/>", 0),
        ("<testcase classname='suite' name='ok'><failure/></testcase>", 1),
        ("", 1),
        ("<testcase classname='suite' name='ok'><skipped/></testcase>", 1),
    ],
)
def test_previously_passing_case_must_still_pass(tmp_path, candidate, code):
    old = tmp_path / "old.xml"
    new = tmp_path / "new.xml"
    old.write_text("<testsuite><testcase classname='suite' name='ok'/></testsuite>")
    new.write_text("<testsuite>" + candidate + "</testsuite>")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(old), str(new)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == code, result.stderr
