"""
server/storage.py — Safe file-writing helpers.

Receives chunks and writes them to disk inside a configurable
upload directory. Creates the directory if it does not exist.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"


def ensure_upload_dir(upload_dir: Path = DEFAULT_UPLOAD_DIR) -> Path:
    """Create the upload directory if it doesn't exist and return its path."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def safe_filename(filename: str) -> str:
    """Sanitise a client-supplied filename to avoid path traversal attacks."""
    return os.path.basename(filename)


class FileWriter:
    """Context-manager wrapper around a binary file handle for chunk writing."""

    def __init__(self, filename: str, upload_dir: Path = DEFAULT_UPLOAD_DIR) -> None:
        self._dir = ensure_upload_dir(upload_dir)
        self._name = safe_filename(filename)
        self._path = self._dir / self._name
        self._fh = None
        self._bytes_written = 0

    # -- context manager --------------------------------------------------
    def __enter__(self) -> "FileWriter":
        self._fh = open(self._path, "wb")
        log.info("[TCP] Opened file for writing: %s", self._path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._fh:
            self._fh.close()
            log.info(
                "[TCP] Closed file: %s (%d bytes written)",
                self._path,
                self._bytes_written,
            )

    # -- public API --------------------------------------------------------
    def write_chunk(self, data: bytes) -> int:
        """Write a chunk and return cumulative bytes written."""
        self._fh.write(data)
        self._bytes_written += len(data)
        return self._bytes_written

    @property
    def bytes_written(self) -> int:
        return self._bytes_written

    @property
    def path(self) -> Path:
        return self._path
