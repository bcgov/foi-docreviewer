"""Fresh-process imports in the production image, without pytest or stubs."""
import importlib
import os
import sys
from datetime import datetime, timezone

assert sys.version_info[:2] == (3, 13), sys.version
assert os.getuid() != 0
print(sys.version)
for name in ("psycopg2", "walrus", "redis", "marshmallow", "maya", "pytz",
             "wrapt", "Crypto", "pypdf"):
    module = importlib.import_module(name)
    print(name, module.__file__)

from walrus import Database
from redis import Redis
from Crypto.Cipher import AES
import maya

assert isinstance(Database(), Redis)
ciphertext, tag = AES.new(b"0" * 16, AES.MODE_GCM, nonce=b"1" * 12).encrypt_and_digest(b"synthetic")
assert AES.new(b"0" * 16, AES.MODE_GCM, nonce=b"1" * 12).decrypt_and_verify(ciphertext, tag) == b"synthetic"
assert maya.MayaDT.from_datetime(datetime(2020, 1, 15, 12, tzinfo=timezone.utc)).datetime(
    to_timezone="America/Vancouver", naive=False).isoformat() == "2020-01-15T04:00:00-08:00"
print("Native imports, Walrus construction, crypto and historical timezone checks passed")
