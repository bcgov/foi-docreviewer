import importlib.util
import os
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

REPOSITORY_ROOT = Path(__file__).parents[3]
TEMPLATE_PATHS = {
    "normal": REPOSITORY_ROOT / "openshift/templates/dedupe-deploy.yaml",
    "large": REPOSITORY_ROOT / "openshift/templates/dedupe-largefiles-deploy.yaml",
}
COMPOSE_PATH = REPOSITORY_ROOT / "docker-compose.yml"
SAMPLE_ENV_PATH = REPOSITORY_ROOT / "sample.env"


def _environment_entries(template_path):
    template = yaml.safe_load(template_path.read_text())
    container = template["objects"][0]["spec"]["template"]["spec"]["containers"][0]
    return container["env"]


def _environment(template_path):
    return {entry["name"]: entry for entry in _environment_entries(template_path)}


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


def test_dedupe_deployments_use_distinct_standard_compression_topics():
    environments = {
        name: _environment(path) for name, path in TEMPLATE_PATHS.items()
    }

    assert environments["normal"]["COMPRESSION_MESSAGING_MODE"]["value"] == "${COMPRESSION_MESSAGING_MODE}"
    assert environments["large"]["COMPRESSION_MESSAGING_MODE"]["value"] == "${COMPRESSION_MESSAGING_MODE}"
    assert environments["normal"]["MESSAGING_STREAM_PREFIX"]["value"] == "${MESSAGING_STREAM_PREFIX}"
    assert environments["large"]["MESSAGING_STREAM_PREFIX"]["value"] == "${MESSAGING_STREAM_PREFIX}"

    assert all(
        environment["COMPRESSION_TOPIC"]["value"] == "${COMPRESSION_TOPIC}"
        for environment in environments.values()
    )
    assert environments["normal"]["COMPRESSION_WORKLOAD"]["value"] == "${COMPRESSION_WORKLOAD}"
    assert environments["large"]["COMPRESSION_WORKLOAD"]["value"] == "${COMPRESSION_WORKLOAD}"

    parameters = {
        name: {
            parameter["name"]: parameter["value"]
            for parameter in yaml.safe_load(path.read_text())["parameters"]
            if parameter["name"]
            in {
                "COMPRESSION_MESSAGING_MODE",
                "MESSAGING_STREAM_PREFIX",
                "COMPRESSION_TOPIC",
                "COMPRESSION_WORKLOAD",
            }
        }
        for name, path in TEMPLATE_PATHS.items()
    }
    assert {
        key: parameters["normal"][key]
        for key in ("COMPRESSION_MESSAGING_MODE", "MESSAGING_STREAM_PREFIX", "COMPRESSION_TOPIC", "COMPRESSION_WORKLOAD")
    } == {
        "COMPRESSION_MESSAGING_MODE": "legacy",
        "MESSAGING_STREAM_PREFIX": "foi",
        "COMPRESSION_TOPIC": "compression",
        "COMPRESSION_WORKLOAD": "normal",
    }
    assert {
        key: parameters["large"][key]
        for key in ("COMPRESSION_MESSAGING_MODE", "MESSAGING_STREAM_PREFIX", "COMPRESSION_TOPIC", "COMPRESSION_WORKLOAD")
    } == {
        "COMPRESSION_MESSAGING_MODE": "legacy",
        "MESSAGING_STREAM_PREFIX": "foi",
        "COMPRESSION_TOPIC": "compression-large",
        "COMPRESSION_WORKLOAD": "large",
    }


def test_dedupe_deployments_require_legacy_compression_stream_keys_without_dual_publish_config():
    environments = {
        name: _environment(path) for name, path in TEMPLATE_PATHS.items()
    }

    for name, path in TEMPLATE_PATHS.items():
        entries = _environment_entries(path)
        names = [entry["name"] for entry in entries]
        assert names.count("COMPRESSION_MESSAGING_MODE") == 1
        assert not any(
            "DUAL" in entry_name and "COMPRESSION" in entry_name
            for entry_name in names
        )
        assert environments[name]["COMPRESSION_MESSAGING_MODE"]["value"] == "${COMPRESSION_MESSAGING_MODE}"
        secret_ref = environments[name]["COMPRESSION_STREAM_KEY"]["valueFrom"][
            "secretKeyRef"
        ]
        assert "optional" not in secret_ref


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
    assert _environment(TEMPLATE_PATHS["large"])["COMPRESSION_TOPIC"]["value"] != sample[
        "COMPRESSION_TOPIC"
    ]


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


def test_dedupe_deployments_document_consumer_delivery_configuration():
    environments = {
        name: _environment(path) for name, path in TEMPLATE_PATHS.items()
    }
    parameters = {
        name: {
            parameter["name"]: parameter["value"]
            for parameter in yaml.safe_load(path.read_text())["parameters"]
            if parameter["name"]
            in {
                "DEDUPE_CONSUMER_GROUP",
                "DEDUPE_CONSUMER_BATCH_SIZE",
                "DEDUPE_CONSUMER_BLOCK_MS",
                "DEDUPE_CONSUMER_MAX_RETRIES",
                "DEDUPE_CONSUMER_RETRY_BACKOFF_MS",
                "DEDUPE_CONSUMER_CLAIM_MIN_IDLE_MS",
                "DEDUPE_DLQ_STREAM",
                "DEDUPE_DLQ_MAXLEN",
                "DEDUPE_LEGACY_CHECKPOINT_KEY",
            }
        }
        for name, path in TEMPLATE_PATHS.items()
    }

    for environment in environments.values():
        assert environment["DEDUPE_CONSUMER_GROUP"]["value"] == "${DEDUPE_CONSUMER_GROUP}"
        assert environment["DEDUPE_CONSUMER_NAME"]["valueFrom"]["fieldRef"][
            "fieldPath"
        ] == "metadata.name"
        assert environment["DEDUPE_CONSUMER_BATCH_SIZE"]["value"] == "${DEDUPE_CONSUMER_BATCH_SIZE}"
        assert environment["DEDUPE_CONSUMER_BLOCK_MS"]["value"] == "${DEDUPE_CONSUMER_BLOCK_MS}"
        assert environment["DEDUPE_CONSUMER_MAX_RETRIES"]["value"] == "${DEDUPE_CONSUMER_MAX_RETRIES}"
        assert environment["DEDUPE_CONSUMER_RETRY_BACKOFF_MS"]["value"] == "${DEDUPE_CONSUMER_RETRY_BACKOFF_MS}"
        assert environment["DEDUPE_CONSUMER_CLAIM_MIN_IDLE_MS"]["value"] == "${DEDUPE_CONSUMER_CLAIM_MIN_IDLE_MS}"
        assert environment["DEDUPE_DLQ_STREAM"]["value"] == "${DEDUPE_DLQ_STREAM}"
        assert environment["DEDUPE_DLQ_MAXLEN"]["value"] == "${DEDUPE_DLQ_MAXLEN}"
        assert environment["DEDUPE_LEGACY_CHECKPOINT_KEY"]["value"] == "${DEDUPE_LEGACY_CHECKPOINT_KEY}"

    assert {
        key: parameters["normal"][key]
        for key in (
            "DEDUPE_CONSUMER_GROUP",
            "DEDUPE_CONSUMER_BATCH_SIZE",
            "DEDUPE_CONSUMER_BLOCK_MS",
            "DEDUPE_CONSUMER_MAX_RETRIES",
            "DEDUPE_CONSUMER_RETRY_BACKOFF_MS",
            "DEDUPE_CONSUMER_CLAIM_MIN_IDLE_MS",
            "DEDUPE_DLQ_STREAM",
            "DEDUPE_DLQ_MAXLEN",
            "DEDUPE_LEGACY_CHECKPOINT_KEY",
        )
    } == {
        "DEDUPE_CONSUMER_GROUP": "dedupe",
        "DEDUPE_CONSUMER_BATCH_SIZE": "10",
        "DEDUPE_CONSUMER_BLOCK_MS": "5000",
        "DEDUPE_CONSUMER_MAX_RETRIES": "5",
        "DEDUPE_CONSUMER_RETRY_BACKOFF_MS": "250",
        "DEDUPE_CONSUMER_CLAIM_MIN_IDLE_MS": "60000",
        "DEDUPE_DLQ_STREAM": "foi:dedupe.dlq",
        "DEDUPE_DLQ_MAXLEN": "10000",
        # Legacy checkpoint seeding is opt-in and must default to empty, so
        # a deployment never seeds implicitly from a shared checkpoint key.
        "DEDUPE_LEGACY_CHECKPOINT_KEY": "",
    }
    assert {
        key: parameters["large"][key]
        for key in (
            "DEDUPE_CONSUMER_GROUP",
            "DEDUPE_CONSUMER_BATCH_SIZE",
            "DEDUPE_CONSUMER_BLOCK_MS",
            "DEDUPE_CONSUMER_MAX_RETRIES",
            "DEDUPE_CONSUMER_RETRY_BACKOFF_MS",
            "DEDUPE_CONSUMER_CLAIM_MIN_IDLE_MS",
            "DEDUPE_DLQ_STREAM",
            "DEDUPE_DLQ_MAXLEN",
            "DEDUPE_LEGACY_CHECKPOINT_KEY",
        )
    } == {
        "DEDUPE_CONSUMER_GROUP": "dedupe",
        "DEDUPE_CONSUMER_BATCH_SIZE": "10",
        "DEDUPE_CONSUMER_BLOCK_MS": "5000",
        "DEDUPE_CONSUMER_MAX_RETRIES": "5",
        "DEDUPE_CONSUMER_RETRY_BACKOFF_MS": "250",
        "DEDUPE_CONSUMER_CLAIM_MIN_IDLE_MS": "60000",
        "DEDUPE_DLQ_STREAM": "foi:dedupe.dlq",
        "DEDUPE_DLQ_MAXLEN": "10000",
        "DEDUPE_LEGACY_CHECKPOINT_KEY": "",
    }


def test_sample_env_documents_legacy_checkpoint_key_disabled_by_default():
    # The sample environment must document the opt-in legacy checkpoint
    # cutover key with an empty default, and must never default it to the
    # shared "$:lastid" key that other still-legacy services/deployments
    # may rely on.
    sample = _sample_environment()

    assert "DEDUPE_LEGACY_CHECKPOINT_KEY" in sample
    assert sample["DEDUPE_LEGACY_CHECKPOINT_KEY"] == ""
    assert sample["DEDUPE_LEGACY_CHECKPOINT_KEY"] != "$:lastid"
