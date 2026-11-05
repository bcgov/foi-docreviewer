import importlib.util
import os
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPOSITORY_ROOT = Path(__file__).parents[3]
COMPOSE_PATH = REPOSITORY_ROOT / "docker-compose.yml"
SAMPLE_ENV_PATH = REPOSITORY_ROOT / "sample.env"


def _compose_dedupe_environment():
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    return compose["services"]["foi-docreviewer-dedupe"]["environment"]


def _sample_environment():
    return {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in SAMPLE_ENV_PATH.read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    }


def clear_dedupe_consumer_environment(monkeypatch):
    for name in (
        "DEDUPE_CONSUMER_GROUP",
        "DEDUPE_CONSUMER_NAME",
        "DEDUPE_CONSUMER_BATCH_SIZE",
        "DEDUPE_CONSUMER_BLOCK_MS",
        "DEDUPE_CONSUMER_MAX_RETRIES",
        "DEDUPE_CONSUMER_RETRY_BACKOFF_MS",
        "DEDUPE_CONSUMER_CLAIM_MIN_IDLE_MS",
        "DEDUPE_DLQ_STREAM",
        "DEDUPE_DLQ_MAXLEN",
        "DEDUPE_LEGACY_CHECKPOINT_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def load_dedupe_settings(monkeypatch):
    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"conversion": [], "dedupe": [], "nonredactable": []}

    def _request(*args, **kwargs):
        return _Response()

    import requests

    monkeypatch.setattr(requests, "request", _request)

    module_name = "foidedupeconfig_under_test"
    spec = importlib.util.spec_from_file_location(
        module_name,
        REPOSITORY_ROOT / "computingservices/DedupeServices/utils/foidedupeconfig.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_local_dedupe_configuration_defaults_to_legacy_with_a_normal_standard_topic():
    compose_environment = _compose_dedupe_environment()
    assert "COMPRESSION_MESSAGING_MODE=${COMPRESSION_MESSAGING_MODE}" in compose_environment
    assert "MESSAGING_STREAM_PREFIX=${MESSAGING_STREAM_PREFIX}" in compose_environment
    assert "COMPRESSION_TOPIC=${COMPRESSION_TOPIC}" in compose_environment
    assert "COMPRESSION_WORKLOAD=${COMPRESSION_WORKLOAD}" in compose_environment
    assert "COMPRESSION_STREAM_KEY=${COMPRESSION_STREAM_KEY}" in compose_environment

    sample = _sample_environment()
    assert sample["COMPRESSION_MESSAGING_MODE"] == "legacy"
    assert sample["MESSAGING_STREAM_PREFIX"] == "foi"
    assert sample["COMPRESSION_TOPIC"] == "compression"
    assert sample["COMPRESSION_WORKLOAD"] == "normal"


def test_consumer_settings_have_safe_defaults(monkeypatch):
    clear_dedupe_consumer_environment(monkeypatch)

    settings = load_dedupe_settings(monkeypatch)

    assert settings.dedupe_consumer_group == "dedupe"
    assert settings.dedupe_consumer_name is None
    assert settings.dedupe_consumer_batch_size == 10
    assert settings.dedupe_consumer_block_ms == 5000
    assert settings.dedupe_consumer_max_retries == 5
    assert settings.dedupe_consumer_retry_backoff_ms == 250
    assert settings.dedupe_consumer_claim_min_idle_ms == 60000
    assert settings.dedupe_dlq_stream == "foi:dedupe.dlq"
    assert settings.dedupe_dlq_maxlen == 10000
    # Legacy checkpoint seeding must be disabled by default: unset/empty,
    # and never a shared "{consumer_id}:lastid"/"$:lastid" style default.
    assert settings.dedupe_legacy_checkpoint_key == ""


@pytest.mark.parametrize(
    "name",
    [
        "DEDUPE_CONSUMER_BATCH_SIZE",
        "DEDUPE_CONSUMER_BLOCK_MS",
        "DEDUPE_CONSUMER_MAX_RETRIES",
        "DEDUPE_CONSUMER_RETRY_BACKOFF_MS",
        "DEDUPE_CONSUMER_CLAIM_MIN_IDLE_MS",
        "DEDUPE_DLQ_MAXLEN",
    ],
)
def test_consumer_numeric_settings_reject_non_positive_values(monkeypatch, name):
    monkeypatch.setenv(name, "0")

    with pytest.raises(ValueError):
        load_dedupe_settings(monkeypatch)


def test_dedupe_dlq_maxlen_can_be_overridden(monkeypatch):
    clear_dedupe_consumer_environment(monkeypatch)
    monkeypatch.setenv("DEDUPE_DLQ_MAXLEN", "25000")

    settings = load_dedupe_settings(monkeypatch)

    assert settings.dedupe_dlq_maxlen == 25000


def test_dedupe_legacy_checkpoint_key_can_be_overridden(monkeypatch):
    clear_dedupe_consumer_environment(monkeypatch)
    monkeypatch.setenv("DEDUPE_LEGACY_CHECKPOINT_KEY", "consumer1:lastid")

    settings = load_dedupe_settings(monkeypatch)

    assert settings.dedupe_legacy_checkpoint_key == "consumer1:lastid"


def test_sample_env_documents_legacy_checkpoint_key_disabled_by_default():
    # The sample environment must document the opt-in legacy checkpoint
    # cutover key with an empty default, and must never default it to the
    # shared "$:lastid" key that other still-legacy services/deployments
    # may rely on.
    sample = _sample_environment()

    assert "DEDUPE_LEGACY_CHECKPOINT_KEY" in sample
    assert sample["DEDUPE_LEGACY_CHECKPOINT_KEY"] == ""
    assert sample["DEDUPE_LEGACY_CHECKPOINT_KEY"] != "$:lastid"
