"""VivaIQ Structured Logging Configuration."""

import logging
import sys


class StructuredFormatter(logging.Formatter):
    """Custom logging formatter outputting clean, readable log messages."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        request_id = getattr(record, "request_id", "-")
        return f"[{timestamp}] [{record.levelname:<7}] [{record.name}] [req:{request_id}] {record.getMessage()}"


def setup_logging(debug: bool = True) -> logging.Logger:
    """Configure root logger for the application."""
    log_level = logging.DEBUG if debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Clear existing handlers to prevent duplicate output
    root_logger.handlers = [handler]

    # Suppress overly chatty external libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)  # logs every plugin it loads at INFO

    logger = logging.getLogger("vivaiq")
    logger.setLevel(log_level)
    return logger


logger = logging.getLogger("vivaiq")
