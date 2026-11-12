"""Fail CI on empty assertion suites or skipped integration checks."""
import sys
import xml.etree.ElementTree as ET

suites = list(ET.parse(sys.argv[1]).iter("testsuite"))
assert sum(int(s.get("tests", 0)) for s in suites) > 0, "No assertions collected"
for attribute in ("skipped", "errors", "failures"):
    assert sum(int(s.get(attribute, 0)) for s in suites) == 0, attribute
