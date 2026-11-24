import json

import pytest


@pytest.mark.parametrize("state,enabled,process,end,notify", [
    ((True, True, False), "True", 0, 0, 0),
    ((True, False, True), "True", 0, 0, 0),
    ((False, False, False), "True", 1, 0, 1),
    ((False, False, False), "False", 1, 0, 0),
    ((True, False, False), "True", 0, 1, 1),
    ((True, False, False), "False", 0, 1, 0),
])
def test_byte_message_job_and_notification_decisions(monkeypatch, state, enabled, process, end, notify):
    from rstreamio.reader import linearharmspdfstitch as reader
    events = []

    class Stitch:
        def ispdfstitchjobstarted(self, jobid, category):
            assert (jobid, category) == (123, "harms")
            return state

        def processmessage(self, message):
            assert message.attributes[0].divisionname == "Alpha"
            events.append("process")

    class Notification:
        def sendnotification(self, message):
            assert message.jobid == 123
            events.append("notification")

    def record(obj, error, finalmessage, **kwargs):
        assert error is True
        assert finalmessage is None
        events.append("error")

    monkeypatch.setattr(reader, "pdfstitchservice", Stitch)
    monkeypatch.setattr(reader, "notificationservice", Notification)
    monkeypatch.setattr(reader, "recordjobend", record)
    monkeypatch.setattr(reader, "notification_enabled", enabled)
    message = {"jobid": "123", "category": "harms", "requestnumber": "SYN-001", "bcgovcode": "SYN",
               "requestid": "1", "ministryrequestid": "2", "createdby": "synthetic",
               "attributes": json.dumps([{"divisionname": "Alpha", "divisionid": 1, "files": []}])}
    reader.handlemessage({k.encode(): v.encode() for k, v in message.items()})
    assert events == ["process"] * process + ["error"] * end + ["notification"] * notify
