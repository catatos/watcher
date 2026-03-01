from __future__ import annotations

import logging
from pathlib import Path


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(log_file: str = "logs/watcher.log", level: int = logging.INFO) -> None:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(level)
    logger.handlers.clear()

    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter(LOG_FORMAT))
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logger.addHandler(stream)
    logger.addHandler(file_handler)
