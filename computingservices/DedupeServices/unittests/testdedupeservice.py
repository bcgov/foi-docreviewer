import os
import sys
from types import ModuleType, SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# The package initializer eagerly imports the database helper, although this
# reuse test replaces all database-facing functions before processing messages.
psycopg2 = sys.modules.setdefault("psycopg2", SimpleNamespace(connect=lambda **kwargs: None))
psycopg2.sql = SimpleNamespace(SQL=lambda query: query)
psycopg2.DatabaseError = Exception


def collaborator_module(name, **attributes):
    module = ModuleType(name)
    for attribute_name, value in attributes.items():
        setattr(module, attribute_name, value)
    return module


sys.modules.setdefault(
    "services.s3documentservice",
    collaborator_module("services.s3documentservice", gets3documenthashcode=None),
)
sys.modules.setdefault(
    "services.dedupedbservice",
    collaborator_module(
        "services.dedupedbservice",
        savedocumentdetails=None,
        recordjobstart=None,
        recordjobend=None,
        updateredactionstatus=None,
        pagecalculatorjobstart=None,
        compressionjobstart=None,
        isbatchcompleted=None,
    ),
)
sys.modules.setdefault(
    "services.documentspagecalculatorservice",
    collaborator_module("services.documentspagecalculatorservice", documentspagecalculatorproducerservice=None),
)
sys.modules.setdefault(
    "rstreamio.redisstreamwriter",
    collaborator_module("rstreamio.redisstreamwriter", redisstreamwriter=None),
)

import services.dedupeservice as dedupe_module
import services.foiredisdedupeconsumer as consumer_module


def source_message():
    return SimpleNamespace(
        incompatible=False,
        documentid=None,
        filename="input.pdf",
        documentmasterid=7,
    )


def test_processmessage_reuses_one_compression_producer_across_messages(monkeypatch):
    producer_instances = []
    compression_calls = []
    page_calculator_calls = []

    class FakeCompressionProducer:
        def __init__(self):
            producer_instances.append(self)

        def producecompressionevent(self, message, jobid):
            compression_calls.append((message, jobid))

    class FakePageCalculatorProducer:
        def createpagecalculatorproducermessage(self, message, pagecount):
            return (message, pagecount)

        def producepagecalculatorevent(self, message, pagecount, jobid):
            page_calculator_calls.append((message, pagecount, jobid))

    monkeypatch.setattr(dedupe_module, "compressionproducerservice", FakeCompressionProducer)
    monkeypatch.setattr(dedupe_module, "documentspagecalculatorproducerservice", FakePageCalculatorProducer)
    monkeypatch.setattr(dedupe_module, "recordjobstart", lambda message: None)
    monkeypatch.setattr(dedupe_module, "gets3documenthashcode", lambda message: ("hash", 3))
    monkeypatch.setattr(dedupe_module, "savedocumentdetails", lambda message, hashcode, pages: (8, True))
    monkeypatch.setattr(dedupe_module, "recordjobend", lambda *args: None)
    monkeypatch.setattr(dedupe_module, "compressionjobstart", lambda message: 11)
    monkeypatch.setattr(dedupe_module, "pagecalculatorjobstart", lambda message: 12)
    dedupe_module._compressionproducer = None

    dedupe_module.processmessage(source_message())
    dedupe_module.processmessage(source_message())

    assert len(producer_instances) == 1
    assert [jobid for _, jobid in compression_calls] == [11, 11]
    assert len(page_calculator_calls) == 2


class StartupReadStream:
    def read(self, last_id, block):
        raise RuntimeError("stop test read loop")


class StartupRedis:
    def __init__(self):
        self.stream_calls = 0
        self.get_calls = 0
        self.set_calls = 0

    def Stream(self, stream_key):
        self.stream_calls += 1
        return StartupReadStream()

    def get(self, key):
        self.get_calls += 1
        return None

    def set(self, key, value):
        self.set_calls += 1


def test_consumer_rejects_invalid_configuration_before_opening_or_advancing_stream(
    monkeypatch,
):
    startup_redis = StartupRedis()

    class InvalidCompressionProducer:
        def __init__(self):
            raise ValueError("compression_messaging_mode is invalid")

    monkeypatch.setattr(consumer_module, "redisstreamdb", startup_redis)
    monkeypatch.setattr(dedupe_module, "compressionproducerservice", InvalidCompressionProducer)
    dedupe_module._compressionproducer = None

    with pytest.raises(ValueError, match="compression_messaging_mode"):
        consumer_module.start("consumer-1")

    assert startup_redis.stream_calls == 0
    assert startup_redis.get_calls == 0
    assert startup_redis.set_calls == 0


def test_consumer_startup_reuses_the_initialized_producer(monkeypatch):
    startup_redis = StartupRedis()
    producer_instances = []

    class FakeCompressionProducer:
        pass

    monkeypatch.setattr(consumer_module, "redisstreamdb", startup_redis)
    monkeypatch.setattr(
        dedupe_module,
        "compressionproducerservice",
        lambda: producer_instances.append(FakeCompressionProducer()) or producer_instances[-1],
    )
    dedupe_module._compressionproducer = None

    with pytest.raises(RuntimeError, match="stop test read loop"):
        consumer_module.start("consumer-1")
    with pytest.raises(RuntimeError, match="stop test read loop"):
        consumer_module.start("consumer-1")

    assert len(producer_instances) == 1
    assert startup_redis.stream_calls == 2
