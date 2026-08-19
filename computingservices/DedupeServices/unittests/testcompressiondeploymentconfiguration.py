from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).parents[3]
TEMPLATE_PATHS = {
    "normal": REPOSITORY_ROOT
    / "openshift/templates/compression/compression-deploy.yaml",
    "large": REPOSITORY_ROOT
    / "openshift/templates/compression/compression-largefiles-deploy.yaml",
}
CRONJOB_PATH = (
    REPOSITORY_ROOT
    / "openshift/templates/compression/compression-reconcile-cronjob.yaml"
)
COMPOSE_PATH = REPOSITORY_ROOT / "docker-compose.yml"
SAMPLE_ENV_PATHS = (
    REPOSITORY_ROOT / "computingservices/CompressionServices/sample.env",
    REPOSITORY_ROOT / "sample.env",
)


def _template_object(template_path):
    return yaml.safe_load(template_path.read_text())["objects"][0]


def _environment(template_path):
    container = _template_object(template_path)["spec"]["template"]["spec"][
        "containers"
    ][0]
    return {entry["name"]: entry for entry in container["env"]}


def _cronjob():
    return _template_object(CRONJOB_PATH)


def _sample_environment(path):
    return {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in path.read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    }


def test_compression_deployments_define_isolated_workload_runtime_settings():
    normal = _environment(TEMPLATE_PATHS["normal"])
    large = _environment(TEMPLATE_PATHS["large"])

    expected_common = {
        "COMPRESSION_MESSAGING_MODE": "legacy",
        "MESSAGING_STREAM_PREFIX": "foi",
        "MESSAGING_CLAIM_INTERVAL": "30s",
        "MESSAGING_MAX_DELIVERY_ATTEMPTS": "5",
        "MESSAGING_SHUTDOWN_TIMEOUT": "25s",
    }
    for name, value in expected_common.items():
        assert normal[name]["value"] == value
        assert large[name]["value"] == value

    assert normal["COMPRESSION_WORKLOAD"]["value"] == "normal"
    assert normal["COMPRESSION_TOPIC"]["value"] == "compression"
    assert normal["MESSAGING_CONSUMER_GROUP"]["value"] == (
        "foi-compression-normal"
    )
    assert normal["COMPRESSION_PROCESSING_TIMEOUT"]["value"] == "15m"
    assert normal["MESSAGING_CLAIM_MIN_IDLE"]["value"] == "17m"

    assert large["COMPRESSION_WORKLOAD"]["value"] == "large"
    assert large["COMPRESSION_TOPIC"]["value"] == "compression-large"
    assert large["MESSAGING_CONSUMER_GROUP"]["value"] == "foi-compression-large"
    assert large["COMPRESSION_PROCESSING_TIMEOUT"]["value"] == "60m"
    assert large["MESSAGING_CLAIM_MIN_IDLE"]["value"] == "62m"

    assert normal["MESSAGING_CONSUMER_GROUP"]["value"] != large[
        "MESSAGING_CONSUMER_GROUP"
    ]["value"]


def test_compression_deployments_keep_legacy_rollback_configuration_without_dual_mode():
    environments = {
        name: _environment(path) for name, path in TEMPLATE_PATHS.items()
    }

    for environment in environments.values():
        names = set(environment)
        assert "COMPRESSION_STREAM_KEY" in names
        assert "COMPRESSION_CHECKPOINT_KEY" in names
        assert not any(
            "DUAL" in entry_name and "COMPRESSION" in entry_name
            for entry_name in names
        )
        stream_secret = environment["COMPRESSION_STREAM_KEY"]["valueFrom"][
            "secretKeyRef"
        ]
        assert "optional" not in stream_secret


def test_compression_reconciliation_cronjob_is_bounded_and_non_overlapping():
    cronjob = _cronjob()
    assert cronjob["kind"] == "CronJob"
    assert cronjob["spec"]["schedule"] == "*/5 * * * *"
    assert cronjob["spec"]["concurrencyPolicy"] == "Forbid"

    job_spec = cronjob["spec"]["jobTemplate"]["spec"]
    assert job_spec["activeDeadlineSeconds"] == 1500
    pod_spec = job_spec["template"]["spec"]
    assert pod_spec["restartPolicy"] == "OnFailure"
    container = pod_spec["containers"][0]
    cronjob_command = container.get("command", []) + container.get("args", [])
    assert cronjob_command[-1] == "reconcile"

    environment = {entry["name"]: entry for entry in container["env"]}
    assert environment["COMPRESSION_RECONCILIATION_NORMAL_AFTER"]["value"] == (
        "20m"
    )
    assert environment["COMPRESSION_RECONCILIATION_LARGE_AFTER"]["value"] == (
        "75m"
    )
    assert environment["COMPRESSION_RECONCILIATION_UNKNOWN_AFTER"]["value"] == (
        "75m"
    )
    assert environment["COMPRESSION_RECONCILIATION_BATCH_SIZE"]["value"] == "100"
    for name in (
        "COMPRESSION_DB_HOST",
        "COMPRESSION_DB_NAME",
        "COMPRESSION_DB_PORT",
        "COMPRESSION_DB_USER",
        "COMPRESSION_DB_PASSWORD",
    ):
        assert "secretKeyRef" in environment[name]["valueFrom"]


def test_local_compression_configuration_uses_normal_runtime_defaults():
    expected = {
        "COMPRESSION_MESSAGING_MODE": "legacy",
        "COMPRESSION_WORKLOAD": "normal",
        "MESSAGING_STREAM_PREFIX": "foi",
        "COMPRESSION_TOPIC": "compression",
        "MESSAGING_CONSUMER_GROUP": "foi-compression-normal",
        "COMPRESSION_PROCESSING_TIMEOUT": "15m",
        "MESSAGING_CLAIM_INTERVAL": "30s",
        "MESSAGING_CLAIM_MIN_IDLE": "17m",
        "MESSAGING_MAX_DELIVERY_ATTEMPTS": "5",
        "MESSAGING_SHUTDOWN_TIMEOUT": "25s",
    }
    for path in SAMPLE_ENV_PATHS:
        sample = _sample_environment(path)
        assert {name: sample[name] for name in expected} == expected

    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    compose_environment = compose["services"]["foi-docreviewer-compression"][
        "environment"
    ]
    for name in expected:
        assert f"{name}=${{{name}}}" in compose_environment
