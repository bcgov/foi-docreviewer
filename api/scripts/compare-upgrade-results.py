"""Fail if baseline-passing tests fail, skip or disappear in the candidate."""

import sys
import xml.etree.ElementTree as ET


def results(path):
    outcomes = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        key = case.get("classname", "") + "::" + case.get("name", "")
        state = "pass"
        for tag in ("failure", "error", "skipped"):
            if case.find(tag) is not None:
                state = tag
                break
        if key in outcomes and outcomes[key] != state:
            raise ValueError("Inconsistent duplicate case: " + key)
        outcomes[key] = state
    if not outcomes:
        raise ValueError("Empty test evidence: " + str(path))
    return outcomes


if __name__ == "__main__":
    baseline, candidate = map(results, sys.argv[1:])
    regressions = [
        name
        for name, state in baseline.items()
        if state == "pass" and candidate.get(name) != "pass"
    ]
    for name in regressions:
        print("REGRESSION:", name, "→", candidate.get(name, "missing"))
    print(
        f"Compared {len(baseline)} baseline and {len(candidate)} candidate cases; {len(regressions)} regressions."
    )
    raise SystemExit(bool(regressions))
