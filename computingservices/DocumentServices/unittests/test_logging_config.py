import logging


def test_get_log_level_defaults_to_warning_when_unset(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    from logging_config import get_log_level

    assert get_log_level() == logging.WARNING


def test_get_log_level_reads_info_from_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    from logging_config import get_log_level

    assert get_log_level() == logging.INFO


def test_get_log_level_falls_back_to_warning_for_invalid_value(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "not-a-level")

    from logging_config import get_log_level

    assert get_log_level() == logging.WARNING
