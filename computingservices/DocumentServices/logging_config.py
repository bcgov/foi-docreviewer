import logging
import os


def get_log_level() -> int:
    level_name = os.getenv("LOG_LEVEL", "WARNING").upper()
    return getattr(logging, level_name, logging.WARNING)


def configure_logging() -> None:
    logging.basicConfig(level=get_log_level())
