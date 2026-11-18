"""Reject shared endpoints before importing the API or running migrations."""

from collections.abc import Mapping
from urllib.parse import urlsplit


def validate_test_environment(environ: Mapping[str, str]) -> None:
    required = {
        "FLASK_ENV": "testing",
        "PYTHON_DOTENV_DISABLED": "1",
        "OSS_S3_HOST": "storage:8333",
        "FOI_RECORD_FORMATS": "http://fixtures:8080/formats",
        "JWT_OIDC_ISSUER": "http://fixtures:8080/realm",
        "JWT_OIDC_JWKS_URI": "http://fixtures:8080/jwks",
        "JWT_OIDC_WELL_KNOWN_CONFIG": "http://fixtures:8080/config",
    }
    for prefix in ("DATABASE", "DATABASE_TEST"):
        required.update(
            {
                f"{prefix}_HOST": "postgres",
                f"{prefix}_NAME": "reviewer_upgrade_test",
                f"{prefix}_PORT": "5432",
            }
        )
    for prefix in ("DOCUMENTSERVICE_REDIS", "ZIPPER_REDIS"):
        required.update({f"{prefix}_HOST": "redis", f"{prefix}_PORT": "6379"})
    for key, value in required.items():
        if environ.get(key) != value:
            raise ValueError(f"{key} must be {value} in isolated verification")
    url = urlsplit(environ.get("DATABASE_TEST_URL", ""))
    if (
        url.scheme not in {"postgresql", "postgresql+psycopg2"}
        or url.hostname != "postgres"
        or url.port != 5432
        or url.path != "/reviewer_upgrade_test"
        or url.query
        or url.fragment
    ):
        raise ValueError("DATABASE_TEST_URL must use the disposable database")
