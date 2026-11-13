"""
Logging: loguru to stdout, plus the repo's Loki logger when it is mounted
(grafana-configs/loki_logger.py, which needs constants.ini). Message text is
citizen data and is never logged.
"""

import sys

from loguru import logger

LEVELS = {
    "DEBUG": "debug",
    "INFO": "info",
    "SUCCESS": "info",
    "WARNING": "warning",
    "ERROR": "error",
    "CRITICAL": "error",
}


def configure(service_name: str) -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO")
    try:
        from loki_logger import LokiLogger
    except Exception as error:
        logger.info(f"Loki logging is off: {error}")
        return

    loki = LokiLogger(service_name=service_name)

    def to_loki(message) -> None:
        record = message.record
        getattr(loki, LEVELS.get(record["level"].name, "info"))(record["message"])

    logger.add(to_loki, level="INFO")
