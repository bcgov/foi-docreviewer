from pathlib import Path

import yaml


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


def test_dedupe_deployments_use_distinct_standard_compression_topics():
    environments = {
        name: _environment(path) for name, path in TEMPLATE_PATHS.items()
    }

    assert environments["normal"]["COMPRESSION_MESSAGING_MODE"]["value"] == "standard"
    assert environments["large"]["COMPRESSION_MESSAGING_MODE"]["value"] == "standard"
    assert environments["normal"]["MESSAGING_STREAM_PREFIX"]["value"] == "foi"
    assert environments["large"]["MESSAGING_STREAM_PREFIX"]["value"] == "foi"

    topics = {
        name: environment["COMPRESSION_TOPIC"]["value"]
        for name, environment in environments.items()
    }
    assert topics == {"normal": "compression", "large": "compression-large"}
    assert topics["normal"] != topics["large"]
    assert {
        f"foi:{topic}" for topic in topics.values()
    } == {"foi:compression", "foi:compression-large"}


def test_dedupe_deployments_keep_legacy_compression_stream_key_without_dual_publish_config():
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
        assert environments[name]["COMPRESSION_MESSAGING_MODE"]["value"] == "standard"
        assert environments[name]["COMPRESSION_STREAM_KEY"]["valueFrom"][
            "secretKeyRef"
        ]["optional"] is True


def test_local_dedupe_configuration_uses_normal_standard_compression_topic():
    compose_environment = _compose_dedupe_environment()
    assert "COMPRESSION_MESSAGING_MODE=${COMPRESSION_MESSAGING_MODE}" in compose_environment
    assert "MESSAGING_STREAM_PREFIX=${MESSAGING_STREAM_PREFIX}" in compose_environment
    assert "COMPRESSION_TOPIC=${COMPRESSION_TOPIC}" in compose_environment
    assert "COMPRESSION_STREAM_KEY=${COMPRESSION_STREAM_KEY}" in compose_environment

    sample = _sample_environment()
    assert sample["COMPRESSION_MESSAGING_MODE"] == "standard"
    assert sample["MESSAGING_STREAM_PREFIX"] == "foi"
    assert sample["COMPRESSION_TOPIC"] == "compression"
    assert _environment(TEMPLATE_PATHS["large"])["COMPRESSION_TOPIC"]["value"] != sample[
        "COMPRESSION_TOPIC"
    ]
