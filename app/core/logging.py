"""Logging configuration"""

import logging
import sys
from pathlib import Path
from .config import settings

# Create logs directory
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure logging format
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

# Create formatter
formatter = logging.Formatter(log_format, date_format)

# Configure root logger
logger = logging.getLogger("kasparro")
logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# File handler
file_handler = logging.FileHandler(log_dir / "app.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get logger for module"""
    return logging.getLogger(f"kasparro.{name}")
