"""
server/udp_server.py — UDP telemetry listener for progress updates.

Listens for PROGRESS datagrams and logs them.
Resilient to malformed packets — never crashes the server.
"""

from __future__ import annotations

import logging
import socket

from shared.protocol import UDP_HOST, UDP_PORT, decode_progress

log = logging.getLogger(__name__)

BUFFER_SIZE = 1024  # progress datagrams are tiny


def start_udp_server(host: str = UDP_HOST, port: int = UDP_PORT) -> None:
    """Start the UDP progress listener. Blocks forever."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    log.info("[UDP] Listening on %s:%d", host, port)

    try:
        while True:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            try:
                info = decode_progress(data)
                log.info(
                    "[UDP] Progress from %s:%d — %s %.1f%%",
                    addr[0],
                    addr[1],
                    info.filename,
                    info.percent,
                )
            except ValueError:
                log.warning("[UDP] Malformed datagram from %s:%d — %r", addr[0], addr[1], data)
    except KeyboardInterrupt:
        log.info("[UDP] Listener shutting down")
    finally:
        sock.close()
