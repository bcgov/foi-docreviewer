import importlib
import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def notification(monkeypatch):
    module = importlib.import_module("services.notificationservice")
    state = SimpleNamespace(events=[], lookups=[], complete=True, error=False)

    class Stream:
        def add(self, fields, id):
            state.events.append(fields)
            return "1-0"

    monkeypatch.setattr(module, "notificationredisstreamdb", SimpleNamespace(Stream=lambda key: Stream()))

    def lookup(jobid, category):
        state.lookups.append((jobid, category))
        return state.complete, state.error

    monkeypatch.setattr(module, "isredlineresponsezipjobcompleted", lookup)
    monkeypatch.setattr(module, "ispdfstichjobcompleted", lambda *args: (*lookup(*args), json.dumps({"stitchedoutput": [
        {"skippedfilecount": 2, "skippedfiles": ["one.pdf", "two.pdf"]},
        {"skippedfilecount": 1, "skippedfiles": ["one.pdf"]}]})))
    return module.notificationservice(), state


@pytest.mark.parametrize("error", [False, True])
def test_harms_skipped_count_names_and_error_flag(notification, message, error):
    service, state = notification
    state.error = error
    state.complete = not error
    service.sendharmsnotification(message)
    assert state.lookups == [("11", "harms")]
    event, = state.events
    assert event == dict(ministryrequestid="2", serviceid="pdfstitchforharms", errorflag="YES" if error else "NO",
                         createdby="synthetic", totalskippedfilecount=3, totalskippedfiles=event["totalskippedfiles"])
    assert set(json.loads(event["totalskippedfiles"])) == {"one.pdf", "two.pdf"}


@pytest.mark.parametrize("category,want,serviceid", [
    ("redline", "redline", "pdfstitchforredline"),
    ("responsepackage", "responsepackage", "pdfstitchforresponsepackage"),
    ("redline_phase1", "redline", "pdfstitchforredline"),
    ("responsepackage_phase2", "responsepackage", "pdfstitchforresponsepackage"),
])
@pytest.mark.parametrize("error", [False, True])
def test_phase_lookup_and_notification_payload(notification, message, category, want, serviceid, error):
    service, state = notification
    state.error = error
    state.complete = not error
    message.category = category
    message.feeoverridereason = "synthetic override"
    service.sendredlineresponsenotification(message)
    assert state.lookups == [("11", want)]
    assert state.events == [dict(ministryrequestid="2", serviceid=serviceid, errorflag="YES" if error else "NO",
                                 createdby="synthetic", feeoverridereason="synthetic override" if want == "responsepackage" else "")]


@pytest.mark.parametrize("category", ["harms", "redline", "responsepackage"])
def test_incomplete_jobs_publish_nothing(notification, message, category):
    service, state = notification
    state.complete = False
    message.category = category
    if category == "harms":
        service.sendharmsnotification(message)
    else:
        service.sendredlineresponsenotification(message)
    assert state.events == []


@pytest.mark.parametrize("category,ready", [("other", True), ("harms", False), ("redline", False), ("other_phase", True)])
def test_dispatch_without_matching_notification_branch(notification, monkeypatch, message, category, ready):
    from services import zipperservice
    service, state = notification
    monkeypatch.setattr(zipperservice, "notificationservice", lambda: service)
    message.category = category
    zipperservice.sendnotification(ready, message)
    assert state.events == []
