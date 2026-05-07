import os
import sys
from datetime import datetime

from loguru import logger
from platformdirs import user_log_dir


def set_up_logging(debug: bool):
    log_dir = user_log_dir("limewire", "masa", ensure_exists=True)
    log_file_path = os.path.join(
        log_dir, f"limewire_{datetime.now().strftime('%Y-%m-%d')}.log"
    )
    radio_log_file_path = os.path.join(
        log_dir,
        f"limewire_radio_dump_{datetime.now().strftime('%Y-%m-%d')}.log",
    )

    log_format = "<green>{time}</> <level>{level}</> {message}"
    log_level = "DEBUG" if debug else "INFO"

    logger.remove()  # Remove preconfigured handlers

    logger.add(
        log_file_path,
        format=log_format,
        level=log_level,
        # Avoid radio dumps to the normal log
        filter=lambda record: not record.get("extra", {}).get("dump", False),
    )
    logger.add(
        sys.stderr,
        colorize=True,
        format=log_format,
        level=log_level,
        # Avoid radio dumps to stderr
        filter=lambda record: not record.get("extra", {}).get("dump", False),
    )

    # Dumps to ensure that radio telemetry is not lost
    logger.add(
        radio_log_file_path,
        format=log_format,
        level=log_level,
        filter=lambda record: record.get("extra", {}).get("dump", False),
    )
