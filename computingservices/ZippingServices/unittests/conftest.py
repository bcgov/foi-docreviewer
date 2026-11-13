"""Offline collaborators only; production dependencies are imported normally."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Avoid loading a developer .env or opening external connections.
for key, value in {"REDIS_HOST": "localhost", "REDIS_PORT": "6379", "REDIS_PASSWORD": "",
                   "NOTIFICATION_REDIS_HOST": "localhost", "NOTIFICATION_REDIS_PORT": "6379",
                   "NOTIFICATION_REDIS_PASSWORD": "", "ZIPPER_STREAM_KEY": "offline-input",
                   "NOTIFICATION_STREAM_KEY": "offline-notifications"}.items():
    os.environ[key] = value


@pytest.fixture
def message():
    from models import zipperproducermessage
    return zipperproducermessage(jobid="11", requestid="1", category="harms", requestnumber="SYN-001",
                                bcgovcode="SYN", createdby="synthetic", ministryrequestid="2",
                                filestozip="[]", finaloutput='{"stitchedoutput": []}', attributes="[]")


@pytest.fixture
def archive(monkeypatch, message):
    from services import zipperservice as service
    state = SimpleNamespace(files={}, uploads=[], statuses=[], paths=[], result=True, error=None)
    monkeypatch.setattr(service, "getcredentialsbybcgovcode", lambda code: object())

    def download(file, credentials):
        if state.error == "download":
            raise OSError("synthetic download failure")
        return state.files[file["s3uripath"]]

    def upload(filename, data, request, code, credentials):
        if state.error == "upload":
            raise OSError("synthetic upload failure")
        state.uploads.append((filename, data))
        return dict(success=state.result, filename=filename, documentpath="https://synthetic/archive.zip")

    monkeypatch.setattr(service, "gets3documentbytearray", download)
    monkeypatch.setattr(service, "uploadbytes", upload)
    monkeypatch.setattr(service, "recordjobstatus", lambda **kwargs: state.statuses.append(kwargs))
    monkeypatch.setattr(service, "savefinaldocumentpath", lambda *args: state.paths.append(args))

    def run(entries):
        message.filestozip = json.dumps([dict(filename=name, s3uripath=uri) for name, uri, data in entries])
        state.files = {uri: data for name, uri, data in entries}
        service.processmessage(message)
        return state

    return run
