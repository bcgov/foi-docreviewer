import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import sys
import pytest


@pytest.fixture
def real_service_modules():
    """Keep historical helper stubs out of tests that import the real worker."""
    prefixes = ('services', 'utils', 'rstreamio')
    def owned(name):
        return any(name == prefix or name.startswith(prefix + '.') for prefix in prefixes)
    previous = {name: module for name, module in sys.modules.items() if owned(name)}
    for name in previous:
        sys.modules.pop(name, None)
    try:
        yield
    finally:
        for name in list(sys.modules):
            if owned(name):
                sys.modules.pop(name, None)
        sys.modules.update(previous)
