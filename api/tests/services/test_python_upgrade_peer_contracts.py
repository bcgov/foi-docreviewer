"""Observe a real redline handoff on the document-service stream."""

import json
from walrus import Database
from reviewer_api.services.radactionservice import redactionservice, jobrecordservice
from reviewer_api.models.default_method_result import DefaultMethodResult


def test_redline_handoff_keeps_payload_and_job_before_publish(monkeypatch):
    database = Database(host="redis", port=6379)
    key = "reviewer-upgrade-document"
    database.delete(key)

    def insert(self, message, userid):
        assert database.xlen(key) == 0
        assert message == {
            "category": "redline",
            "ministryrequestid": 910,
            "inputfiles": [
                {
                    "phase": None,
                    "files": [
                        {
                            "filename": "synthetic.pdf",
                            "s3uripath": "s3://synthetic/test.pdf",
                        }
                    ],
                }
            ],
        }
        assert userid == "synthetic@idir"
        return DefaultMethodResult(True, "created", 910)

    monkeypatch.setattr(jobrecordservice, "insertpdfstitchjobstatus", insert)
    result = redactionservice().triggerdownloadredlinefinalpackage(
        {
            "category": "redline",
            "ministryrequestid": 910,
            "requestnumber": "SYN-910",
            "bcgovcode": "SYN",
            "requesttype": "General",
            "redactionlayerid": 1,
            "summarydocuments": [],
            "attributes": [
                {
                    "phase": None,
                    "files": [
                        {
                            "filename": "synthetic.pdf",
                            "s3uripath": "s3://synthetic/test.pdf",
                        }
                    ],
                }
            ],
        },
        {"userid": "synthetic@idir"},
    )
    assert result.success
    entries = database.xrange(key)
    assert len(entries) == 1
    message = {k.decode(): v.decode() for k, v in entries[0][1].items()}
    assert message["jobid"] == "910"
    assert message["requestid"] == "-1"
    assert message["phase"] == ""
    assert json.loads(message["filestozip"]) == [
        {"filename": "synthetic.pdf", "s3uripath": "s3://synthetic/test.pdf"}
    ]
    assert json.loads(message["summarydocuments"]) == []
