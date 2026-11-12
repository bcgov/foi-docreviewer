"""Fresh-process checks: never run under the unit suite's module stubs."""
import importlib
import json
import os
from pathlib import Path
import platform
import ssl

for name in ('psycopg2', 'redis', 'walrus', 'boto3', 'requests', 'wrapt',
             'Crypto', 'pypdf', 'marshmallow'):
    importlib.import_module(name)

from rstreamio.message.schemas.redactionsummary import get_in_summary_object
summary = get_in_summary_object('{"sorteddocuments": [1], "pkgdocuments": []}')
assert summary.sorteddocuments == [1]
assert summary.pkgdocuments == []
assert os.getuid() != 0
assert ssl.create_default_context().get_ca_certs()
for template in Path('templates').glob('*.docx'):
    assert template.read_bytes().startswith(b'PK')
assert len(list(Path('templates').glob('*.docx'))) == 3
print(json.dumps({'python': platform.python_version(), 'os': platform.freedesktop_os_release(),
                  'uid': os.getuid(), 'imports': 'passed', 'templates': 3}))
