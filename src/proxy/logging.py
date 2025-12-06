import os
import sys

from loguru import logger
from platformdirs import user_log_dir


def set_up_logging(debug: bool = False):
    log_dir = user_log_dir("proxy", "masa", ensure_exists=True)
    log_file_path = os.path.join(log_dir, "proxy.log")

    log_format = "<green>{time}</> <level>{level}</> {message}"
    log_level = "DEBUG" if debug else "INFO"

    logger.remove()  # Remove preconfigured handlers
    logger.add(log_file_path, format=log_format, level=log_level)
    logger.add(sys.stderr, colorize=True, format=log_format, level=log_level)
