"""Exercise image reversion against disposable DB/Redis effects only."""

import sys
from sqlalchemy import text
from reviewer_api import create_app
from reviewer_api.models import db
from reviewer_api.models.Annotations import Annotation
from reviewer_api.models.DocumentMaster import DocumentMaster
from reviewer_api.models.Documents import Document
from reviewer_api.services.external.eventqueueproducerservice import (
    eventqueueproducerservice,
)

app = create_app("testing")
with app.app_context():
    if sys.argv[1] == "write":
        result = DocumentMaster.create(
            DocumentMaster(
                documentmasterid=920001,
                filepath="s3://synthetic/rollback/test.pdf",
                ministryrequestid=920,
                isredactionready=True,
            )
        )
        assert result.success
        db.session.add(
            Document(
                documentid=920001,
                version=1,
                filename="rollback.pdf",
                documentmasterid=920001,
                foiministryrequestid=920,
                createdby={},
                statusid=1,
                incompatible=False,
            )
        )
        db.session.commit()
        result = Annotation.saveannotations(
            [
                {
                    "name": "upgrade-rollback",
                    "docid": 920001,
                    "docversion": 1,
                    "page": 0,
                    "xml": "<redact />",
                }
            ],
            1,
            {"userid": "synthetic@idir"},
        )
        assert result.success
        assert (
            eventqueueproducerservice()
            .add("reviewer-upgrade-rollback", {"requestid": "920", "state": "saved"})
            .success
        )
    elif sys.argv[1] == "read":
        assert DocumentMaster.filteroriginalnoconversionfiles(920) == [920001]
        rows = Annotation.getrequestannotations(920, [1])
        assert len(rows) == 1 and rows[0]["annotation"] == "<redact />"
        assert rows[0]["annotationname"] == "upgrade-rollback"
        entries = eventqueueproducerservice.db.xrange("reviewer-upgrade-rollback")
        assert len(entries) == 1 and entries[0][1] == {
            b"requestid": b"920",
            b"state": b"saved",
        }
    else:
        raise ValueError("Expected write or read")
print("Disposable rollback " + sys.argv[1] + " passed")
