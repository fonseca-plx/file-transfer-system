"""
client/tcp_client.py — TCP client that uploads a file to the server.

Protocol flow:
  1. Connect to TCP server
  2. Send HEADER (length-prefixed) with filename + filesize
  3. Send raw DATA in CHUNK_SIZE increments
  4. Send END marker (length-prefixed)

Returns a generator of (bytes_sent, total) tuples so callers can
observe progress (used by sender.py to also push UDP telemetry).
"""

from __future__ import annotations

import logging
import os
import socket
from typing import Generator

from shared.protocol import (
    CHUNK_SIZE,
    TCP_HOST,
    TCP_PORT,
    encode_end,
    encode_header,
    send_msg,
)

log = logging.getLogger(__name__)


def upload_file(
    filepath: str,
    host: str = TCP_HOST,
    port: int = TCP_PORT,
) -> Generator[tuple[int, int], None, None]:
    """Stream *filepath* to the TCP server, yielding (bytes_sent, total).

    Usage::

        for sent, total in upload_file("report.pdf"):
            print(f"{sent}/{total}")
    """
    filesize = os.path.getsize(filepath)
    filename = os.path.basename(filepath)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        log.info("[TCP] Connected to %s:%d", host, port)

        # ── 1. HEADER ──────────────────────────────────────────────
        send_msg(sock, encode_header(filename, filesize))
        log.info("[TCP] Sent HEADER — file=%s size=%d", filename, filesize)

        # ── 2. DATA chunks ─────────────────────────────────────────
        bytes_sent = 0
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                sock.sendall(chunk)
                bytes_sent += len(chunk)
                log.debug("[TCP] Sent chunk — %d / %d bytes", bytes_sent, filesize)
                yield bytes_sent, filesize

        # ── 3. END marker ──────────────────────────────────────────
        send_msg(sock, encode_end())
        log.info("[TCP] Sent END — upload finished")

    except Exception:
        log.exception("[TCP] Error during upload")
        raise
    finally:
        sock.close()
        log.info("[TCP] Connection closed")
