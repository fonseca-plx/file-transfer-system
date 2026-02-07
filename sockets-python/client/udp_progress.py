"""
client/udp_progress.py — Sends progress telemetry over UDP.

UDP is "fire and forget": packet loss must NEVER interrupt the TCP upload.
"""

from __future__ import annotations

import logging
import socket

from shared.protocol import UDP_HOST, UDP_PORT, encode_progress

log = logging.getLogger(__name__)


class ProgressReporter:
    """Sends PROGRESS datagrams to the UDP telemetry server."""

    def __init__(self, host: str = UDP_HOST, port: int = UDP_PORT) -> None:
        self._addr = (host, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def report(self, filename: str, percent: float) -> None:
        """Send a single progress update. Failures are silently logged."""
        try:
            data = encode_progress(filename, percent)
            self._sock.sendto(data, self._addr)
            log.debug("[UDP] Sent progress — %s %.1f%%", filename, percent)
        except OSError as exc:
            # UDP loss must not crash the transfer
            log.warning("[UDP] Failed to send progress: %s", exc)

    def close(self) -> None:
        self._sock.close()
