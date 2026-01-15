import os
import sys
from datetime import datetime

from loguru import logger
from platformdirs import user_log_dir


def set_up_logging(debug: bool):
    log_dir = user_log_dir("Hydrant", "MASA", ensure_exists=True)
    log_file_path = os.path.join(
        log_dir, f"hydrant_{datetime.now().strftime('%Y-%m-%d')}.log"
    )
    event_file_path = os.path.join(
        log_dir, f"events_{datetime.now().strftime('%Y-%m-%d')}.log"
    )

    log_format = "<green>{time}</> <level>{level}</> {message}"
    log_level = "DEBUG" if debug else "INFO"

    logger.remove()  # Remove preconfigured handlers
    logger.add(log_file_path, format=log_format, level=log_level, enqueue=True)
    logger.add(sys.stderr, colorize=True, format=log_format, level=log_level, enqueue=True)
    print(f"Logging to {log_dir}") # This should stay as a print statement, as it is just a message to aid in finding the log directory
    logger.level("EVENT", no=1, color="<white>")
    logger.add(event_file_path, format=log_format, level="EVENT", filter= lambda r: r["level"].name == "EVENT", enqueue=True)