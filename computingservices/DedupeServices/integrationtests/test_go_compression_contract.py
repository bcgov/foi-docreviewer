import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import redis


DEDUPE_SERVICES_DIRECTORY = Path(__file__).resolve().parents[1]
FIXTURE_DIRECTORY = Path(__file__).resolve().parent
GO_CONSUMER_DIRECTORY = FIXTURE_DIRECTORY / "go-consumer"
COMPOSE_FILE = FIXTURE_DIRECTORY / "docker-compose.yml"
REDIS_PORT = 16379
COMPRESSION_TOPICS = ("compression", "compression-large")

sys.path.insert(0, str(DEDUPE_SERVICES_DIRECTORY))

from rstreamio.compressionevents import (  # noqa: E402
    CompressionEventDefinition,
    StandardCompressionPublisher,
)


@pytest.fixture(scope="module")
def redis_client():
    if os.getenv("RUN_COMPRESSION_CONTRACT_TESTS") != "1":
        pytest.skip("set RUN_COMPRESSION_CONTRACT_TESTS=1 to run the Redis/Go contract suite")

    project_name = "foimod5199compressioncontract"
    subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            project_name,
            "-f",
            str(COMPOSE_FILE),
            "up",
            "-d",
            "--wait",
        ],
        check=True,
    )
    client = redis.Redis(host="127.0.0.1", port=REDIS_PORT, decode_responses=False)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if client.ping():
                break
            time.sleep(0.2)
        else:
            pytest.fail("Redis 7 fixture did not become ready")
        yield client
    finally:
        client.close()
        subprocess.run(
            [
                "docker",
                "compose",
                "-p",
                project_name,
                "-f",
                str(COMPOSE_FILE),
                "down",
                "--volumes",
            ],
            check=False,
        )


def publish(redis_client, topic, payload):
    publisher = StandardCompressionPublisher(
        redis_client,
        "foi",
        CompressionEventDefinition(
            topic=topic,
            event_type="document.compression.requested",
            schema_version="1.0.0",
            source="foi-docreviewer.dedupe",
        ),
    )
    return publisher.publish(payload, correlation_id=f"{topic}-correlation")


def clear_stream(redis_client, topic):
    redis_client.delete(f"foi:{topic}", f"foi:{topic}.dlq")


def clear_compression_streams(redis_client):
    for topic in COMPRESSION_TOPICS:
        clear_stream(redis_client, topic)


def assert_stream_isolation(redis_client, selected_topic):
    other_topic = next(topic for topic in COMPRESSION_TOPICS if topic != selected_topic)

    assert redis_client.xlen(f"foi:{selected_topic}") == 1
    assert redis_client.xlen(f"foi:{other_topic}") == 0
    assert redis_client.xrange(f"foi:{other_topic}", "-", "+") == []


def consume(topic, expect_dispatch):
    completed = subprocess.run(
        [
            "go",
            "run",
            ".",
            "-topic",
            topic,
            "-group",
            f"contract-{topic}",
            "-expect-dispatch",
            str(expect_dispatch).lower(),
        ],
        cwd=GO_CONSUMER_DIRECTORY,
        env={**os.environ, "REDIS_ADDRESS": f"127.0.0.1:{REDIS_PORT}"},
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def assert_no_pending(redis_client, topic):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        pending = redis_client.xpending_range(
            f"foi:{topic}", f"contract-{topic}", "-", "+", 10
        )
        if not pending:
            return
        time.sleep(0.1)
    pytest.fail(f"typed consumer left pending entries on foi:{topic}: {pending}")


@pytest.mark.parametrize("topic", COMPRESSION_TOPICS)
def test_standard_python_events_are_dispatched_to_the_go_typed_consumer(redis_client, topic):
    """A regression in Python envelope typing or topic routing breaks Go dispatch."""
    clear_compression_streams(redis_client)
    payload = {
        "jobid": 5199,
        "documentmasterid": 42,
        "filename": "typed-contract.pdf",
        "incompatible": False,
        "attributes": {"pages": 3, "details": {"classification": "open"}},
    }

    published = publish(redis_client, topic, payload)
    assert_stream_isolation(redis_client, topic)
    consumed = consume(topic, expect_dispatch=True)

    assert consumed == {
        "acknowledged": True,
        "attributes": {"details": {"classification": "open"}, "pages": 3},
        "dispatched": True,
        "document_master_id": 42,
        "event_id": published.event_id,
        "filename": "typed-contract.pdf",
        "incompatible": False,
        "job_id": 5199,
        "topic": topic,
    }
    assert_no_pending(redis_client, topic)


def test_standard_consumer_does_not_dispatch_a_legacy_flat_entry(redis_client):
    """A legacy flat entry must not be mistaken for a typed standard event."""
    clear_stream(redis_client, "compression")
    redis_client.xadd(
        "foi:compression",
        {
            "jobid": "5199",
            "documentmasterid": "42",
            "filename": "legacy-flat.pdf",
            "incompatible": "false",
            "attributes": '{"pages": 3}',
        },
    )

    consumed = consume("compression", expect_dispatch=False)

    assert consumed == {"acknowledged": True, "dispatched": False, "topic": "compression"}
    assert_no_pending(redis_client, "compression")
