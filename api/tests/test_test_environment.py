"""Guard prevents accidental writes to shared services before API imports."""

import importlib.util
from pathlib import Path
import pytest


def guard():
    path = Path(__file__).parents[1] / "scripts/check_test_environment.py"
    assert path.exists(), "isolation guard is missing"
    spec = importlib.util.spec_from_file_location("upgrade_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_test_environment


def safe():
    return dict(
        FLASK_ENV="testing",
        PYTHON_DOTENV_DISABLED="1",
        DATABASE_HOST="postgres",
        DATABASE_NAME="reviewer_upgrade_test",
        DATABASE_PORT="5432",
        DATABASE_TEST_HOST="postgres",
        DATABASE_TEST_NAME="reviewer_upgrade_test",
        DATABASE_TEST_PORT="5432",
        DATABASE_TEST_URL="postgresql://postgres:test@postgres:5432/reviewer_upgrade_test",
        DOCUMENTSERVICE_REDIS_HOST="redis",
        DOCUMENTSERVICE_REDIS_PORT="6379",
        FOI_RECORD_FORMATS="http://fixtures:8080/formats",
        JWT_OIDC_ISSUER="http://fixtures:8080/realm",
        JWT_OIDC_JWKS_URI="http://fixtures:8080/jwks",
        JWT_OIDC_WELL_KNOWN_CONFIG="http://fixtures:8080/config",
        ZIPPER_REDIS_HOST="redis",
        ZIPPER_REDIS_PORT="6379",
        OSS_S3_HOST="storage:8333",
    )


def test_complete_fake_configuration_is_accepted():
    guard()(safe())


@pytest.mark.parametrize(
    "key,value",
    [
        ("FLASK_ENV", "production"),
        ("PYTHON_DOTENV_DISABLED", "0"),
        ("DATABASE_HOST", "shared-db"),
        ("DATABASE_TEST_HOST", "shared-db"),
        ("DATABASE_TEST_URL", "postgresql://postgres:test@shared:5432/production"),
        ("DOCUMENTSERVICE_REDIS_HOST", "shared"),
        ("ZIPPER_REDIS_HOST", "shared"),
        ("OSS_S3_HOST", "real-storage.example"),
        ("DATABASE_NAME", "production"),
        ("FOI_RECORD_FORMATS", "https://shared/formats"),
    ],
)
def test_endpoint_overrides_are_rejected(key, value):
    environ = safe()
    environ[key] = value
    check = guard()
    with pytest.raises(ValueError):
        check(environ)


def test_missing_isolation_is_rejected():
    check = guard()
    with pytest.raises(ValueError):
        check({})
