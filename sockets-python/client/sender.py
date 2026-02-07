"""
client/sender.py — High-level orchestrator: TCP upload + UDP progress.

Ties tcp_client and udp_progress together so the caller only needs::

    python -m client.sender <filepath>
"""

from __future__ import annotations

import logging
import os
import sys

from client.tcp_client import upload_file
from client.udp_progress import ProgressReporter
from shared.protocol import TCP_HOST, TCP_PORT, UDP_HOST, UDP_PORT

log = logging.getLogger(__name__)

# Send a UDP progress datagram every N chunks (avoids flooding)
PROGRESS_EVERY_N_CHUNKS = 5


def send_file(
    filepath: str,
    tcp_host: str = TCP_HOST,
    tcp_port: int = TCP_PORT,
    udp_host: str = UDP_HOST,
    udp_port: int = UDP_PORT,
) -> None:
    """Upload *filepath* over TCP while reporting progress over UDP."""
    if not os.path.isfile(filepath):
        log.error("File not found: %s", filepath)
        sys.exit(1)

    filename = os.path.basename(filepath)
    reporter = ProgressReporter(udp_host, udp_port)
    chunk_count = 0

    try:
        for bytes_sent, total in upload_file(filepath, tcp_host, tcp_port):
            chunk_count += 1
            percent = (bytes_sent / total) * 100

            # Throttle UDP: send every N chunks and always at 100 %
            if chunk_count % PROGRESS_EVERY_N_CHUNKS == 0 or bytes_sent == total:
                reporter.report(filename, percent)
                log.info("[SEND] %s — %.1f%% (%d/%d bytes)", filename, percent, bytes_sent, total)

        log.info("[SEND] Transfer complete: %s", filename)
    finally:
        reporter.close()


# ── CLI entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )

    if len(sys.argv) < 2:
        print(f"Usage: python -m client.sender <filepath>")
        sys.exit(1)

    send_file(sys.argv[1])
