import os

from config.settings import Settings


def test_settings_construct_with_no_environment_at_all(monkeypatch):
    """
    There are no required fields. The worker must be runnable with zero
    configuration — a new user should be able to `python main.py` against a
    default local Redis.
    """
    for key in list(os.environ):
        if key.startswith(
            ("DATABASE", "REDIS", "STREAM", "OUTPUT", "CONSUMER", "HEALTH", "STATE",
             "WORK", "MAX_PDF", "S3")
        ):
            monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.REDIS_STREAM_URL == "redis://localhost:6379/1"
    assert settings.STREAM_NAME == "pdf.preprocessing.requests"
    assert settings.OUTPUT_STREAM_NAME == "pdf.preprocessing.completed"
    assert settings.HEALTH_PORT == 8000
    assert settings.MAX_PDF_BYTES == 100 * 1024 * 1024
    assert not hasattr(settings, "DATABASE_URL")


def test_dlq_stream_derives_from_stream_name():
    s = Settings(_env_file=None, STREAM_NAME="x.events", DLQ_STREAM_NAME="")
    assert s.dlq_stream == "x.events:dlq"
    s2 = Settings(_env_file=None, DLQ_STREAM_NAME="custom:dlq")
    assert s2.dlq_stream == "custom:dlq"
