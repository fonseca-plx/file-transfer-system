"""
server/tcp_server.py — TCP server that receives file uploads.

Protocol flow (per connection):
  1. Receive HEADER message  →  filename + filesize
  2. Receive raw DATA chunks  →  write to disk via storage.FileWriter
  3. Receive END message      →  finalise
"""

from __future__ import annotations

import logging
import socket
import threading

from shared.protocol import (
    CHUNK_SIZE,
    END_TAG,
    TCP_HOST,
    TCP_PORT,
    decode_header,
    recv_msg,
)
from server.storage import FileWriter

log = logging.getLogger(__name__)


def _handle_client(conn: socket.socket, addr: tuple) -> None:
    """Handle a single client connection in its own thread."""
    log.info("[TCP] Connection accepted from %s:%d", *addr)
    try:
        # ── Step 1: receive HEADER ──────────────────────────────────
        header_raw = recv_msg(conn)
        if header_raw is None:
            log.warning("[TCP] Client disconnected before sending header")
            return

        info = decode_header(header_raw)
        log.info(
            "[TCP] Transfer started — file=%s size=%d bytes",
            info.filename,
            info.filesize,
        )

        # ── Step 2: receive DATA chunks ─────────────────────────────
        with FileWriter(info.filename) as writer:
            remaining = info.filesize
            while remaining > 0:
                chunk_size = min(CHUNK_SIZE, remaining)
                data = conn.recv(chunk_size)
                if not data:
                    log.error("[TCP] Client disconnected mid-transfer!")
                    return
                writer.write_chunk(data)
                remaining -= len(data)
                log.debug(
                    "[TCP] Chunk received — %d / %d bytes",
                    writer.bytes_written,
                    info.filesize,
                )

            # ── Step 3: receive END marker ──────────────────────────
            end_raw = recv_msg(conn)
            if end_raw and end_raw.decode("utf-8").strip() == END_TAG:
                log.info("[TCP] Upload complete — %s", writer.path)
            else:
                log.warning("[TCP] Missing END marker, file may be incomplete")

    except Exception:
        log.exception("[TCP] Error handling client %s:%d", *addr)
    finally:
        conn.close()
        log.info("[TCP] Connection closed for %s:%d", *addr)


def start_tcp_server(host: str = TCP_HOST, port: int = TCP_PORT) -> None:
    """Start the TCP server. Blocks forever, spawning a thread per client."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(5)
    log.info("[TCP] Server listening on %s:%d", host, port)

    try:
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=_handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        log.info("[TCP] Server shutting down")
    finally:
        server_sock.close()
