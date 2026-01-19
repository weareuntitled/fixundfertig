import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


_LOG_FILE_NAME = "fixundfertig.log"
_MAX_LOG_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5


def setup_logging() -> None:
    log_level = logging.DEBUG if os.getenv("FF_DEBUG") == "1" else logging.INFO
    root_logger = logging.getLogger()
    if getattr(root_logger, "_ff_logging_configured", False):
        root_logger.setLevel(log_level)
        for handler in root_logger.handlers:
            handler.setLevel(log_level)
        return

    log_dir = Path("./data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_dir / _LOG_FILE_NAME,
        maxBytes=_MAX_LOG_BYTES,
        backupCount=_BACKUP_COUNT,
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    root_logger._ff_logging_configured = True
