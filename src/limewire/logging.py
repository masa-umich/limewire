import logging
import logging.handlers
import os

from platformdirs import user_log_dir


class ErrorCodeFormatter(logging.Formatter):
    def format(self, record):
        # Ensure error_code exists
        if not hasattr(record, "error_code"):
            record.error_code = "Unknown"

        return super().format(record)


def setup_logging(verbosity: str):
    # TODO: confirm this
    log_dir = user_log_dir("limewire", "masa")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "limewire.log")

    logging_level = (
        logging.DEBUG
        if verbosity == "debug"
        else logging.ERROR
        if verbosity == "sparse"
        else logging.INFO
    )

    log_format = "%(asctime)s.%(msecs)03d %(error_code)s %(message)s"
    log_dateFmt = "%Y-%m-%dT%H:%M:%S"
    formatter = ErrorCodeFormatter(log_format, datefmt=log_dateFmt)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging_level)

    # TODO: Change address once port is chosen
    syslog_handler = logging.handlers.SysLogHandler(address=("localhost", 1234))
    syslog_handler.setFormatter(formatter)
    syslog_handler.setLevel(logging_level)

    UNCONDITIONAL = logging.CRITICAL + 1
    logging.addLevelName(UNCONDITIONAL, "UNCONDITIONAL")

    logging.basicConfig(
        level=logging_level,
        handlers=[file_handler, stream_handler, syslog_handler],
    )
