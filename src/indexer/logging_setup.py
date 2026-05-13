"""Application logging — rotating file in %LocalAppData%\\Indexer\\logs."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def log_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    d = base / "Indexer" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def configure() -> Path:
    """Initialise the root logger. Returns the path to the live log file."""
    path = log_dir() / "indexer.log"
    root = logging.getLogger()
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return path
    root.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    fh = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    return path
