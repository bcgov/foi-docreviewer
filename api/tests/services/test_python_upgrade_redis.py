"""Real stream protocol checks with disposable Redis."""

import pytest
from walrus import Database
from reviewer_api.services.external.eventqueueproducerservice import (
    eventqueueproducerservice,
)
from reviewer_api.services.external.documentserviceproducerservice import (
    documentserviceproducerservice,
)


@pytest.mark.parametrize("kind", ["zipper", "document"])
def test_producers_preserve_payload_and_return_decoded_id(kind):
    database = Database(host="redis", port=6379)
    payload = {"requestid": "910", "data": '{"documents":[910001]}'}
    key = "reviewer-upgrade-document" if kind == "document" else "reviewer-upgrade-zip"
    database.delete(key)
    result = (
        documentserviceproducerservice().add(payload)
        if kind == "document"
        else eventqueueproducerservice().add(key, payload)
    )
    assert result.success and isinstance(result.identifier, str)
    entries = database.xrange(key)
    assert len(entries) == 1
    assert entries[0] == (
        result.identifier.encode(),
        {b"requestid": b"910", b"data": b'{"documents":[910001]}'},
    )


@pytest.mark.parametrize(
    "producer", [eventqueueproducerservice, documentserviceproducerservice]
)
def test_redis_failure_preserves_result(producer, monkeypatch):
    monkeypatch.setattr(
        producer, "db", Database(host="redis", port=1, socket_connect_timeout=0.2)
    )
    result = (
        producer().add("upgrade", {"requestid": "910"})
        if producer is eventqueueproducerservice
        else producer().add({"requestid": "910"})
    )
    assert result.success is False and result.identifier == -1
