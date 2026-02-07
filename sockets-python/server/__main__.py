"""
server/__main__.py — Unified server entry point.

Starts both the TCP file-receiving server and the UDP progress
listener in separate threads, then blocks until Ctrl-C.

Usage::

    cd sockets-python/
    python -m server
"""

from __future__ import annotations

import logging
import threading

from server.tcp_server import start_tcp_server
from server.udp_server import start_udp_server
from shared.protocol import TCP_HOST, TCP_PORT, UDP_HOST, UDP_PORT


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )

    log = logging.getLogger(__name__)

    # Start UDP listener in a daemon thread
    udp_thread = threading.Thread(
        target=start_udp_server,
        args=(UDP_HOST, UDP_PORT),
        daemon=True,
        name="udp-listener",
    )
    udp_thread.start()
    log.info("[MAIN] UDP thread started")

    # Run TCP server on the main thread (blocks until Ctrl-C)
    log.info("[MAIN] Starting TCP server on main thread")
    try:
        start_tcp_server(TCP_HOST, TCP_PORT)
    except KeyboardInterrupt:
        log.info("[MAIN] Server stopped by user")


if __name__ == "__main__":
    main()
