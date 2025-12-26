"""Application logging with Loguru + Slack notifications."""

import logging
import sys
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings

LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[name]}:{function}:{line} | {message}"

# Track if logging is already configured to prevent duplicates
_logging_configured = False


class InterceptHandler(logging.Handler):
    """Redirect stdlib logs to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_name == "emit":
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _slack_sink(message: Any) -> None:
    if not settings.SLACK_WEBHOOK_URL:
        return

    record = message.record
    name = record["extra"].get("name") or record.get("name", "app")
    text = f"[{record['level'].name}] {name}:{record['function']}:{record['line']}\n{record['message']}"
    try:
        httpx.post(
            settings.SLACK_WEBHOOK_URL,
            json={"text": text},
            timeout=5.0,
        )
    except Exception:
        # Avoid recursive logging on Slack failures
        pass


def configure_logging() -> None:
    global _logging_configured
    
    # Prevent duplicate configuration
    if _logging_configured:
        return
    _logging_configured = True
    
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    level = (settings.LOG_LEVEL or "INFO").strip().upper()
    level = {
        "WARN": "WARNING",
        "FATAL": "CRITICAL",
    }.get(level, level)
    if level not in {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}:
        level = "INFO"

    logger.remove()
    # Provide a safe default for log formatting.
    logger.configure(extra={"name": "app"})
    logger.add(
        sys.stdout,
        level=level,
        format=LOG_FORMAT,
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        log_dir / "app.log",
        level=level,
        format=LOG_FORMAT,
        rotation="10 MB",
        retention="14 days",
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )

    if settings.SLACK_WEBHOOK_URL:
        logger.add(_slack_sink, level="ERROR", enqueue=True)

    # Intercept stdlib logging and disable propagation to avoid duplicates
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Disable uvicorn's default logging to prevent duplicates
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        logging.getLogger(logger_name).handlers = [InterceptHandler()]
        logging.getLogger(logger_name).propagate = False


def get_logger(name: str) -> logger.__class__:
    return logger.bind(name=name)


configure_logging()
