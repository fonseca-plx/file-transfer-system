"""
shared/protocol.py — Application-level protocol for the sockets file-transfer system.

Wire formats
============

TCP (reliable channel — file data)
-----------------------------------
1. HEADER  →  "HEADER|<filename>|<filesize>\n"
2. DATA    →  raw bytes, sent in CHUNK_SIZE increments
3. END     →  "END\n"

UDP (unreliable channel — progress telemetry)
----------------------------------------------
1. PROGRESS →  "PROGRESS|<filename>|<percent>\n"
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# ── Network defaults ────────────────────────────────────────────────
TCP_HOST = "localhost"
TCP_PORT = 5000
UDP_HOST = "localhost"
UDP_PORT = 5001
CHUNK_SIZE = 4096  # bytes per TCP data chunk

# ── Message type tags ───────────────────────────────────────────────
HEADER_TAG = "HEADER"
END_TAG = "END"
PROGRESS_TAG = "PROGRESS"

DELIMITER = "|"
LINE_END = "\n"


# ── TCP helpers ─────────────────────────────────────────────────────
def encode_header(filename: str, filesize: int) -> bytes:
    """Build the HEADER line that initiates a file transfer."""
    msg = f"{HEADER_TAG}{DELIMITER}{filename}{DELIMITER}{filesize}{LINE_END}"
    return msg.encode("utf-8")


def encode_end() -> bytes:
    """Build the END marker that closes a file transfer."""
    return f"{END_TAG}{LINE_END}".encode("utf-8")


@dataclass
class HeaderInfo:
    filename: str
    filesize: int


def decode_header(raw: bytes) -> HeaderInfo:
    """Parse a HEADER line received over TCP.

    Raises ValueError if the line is malformed.
    """
    text = raw.decode("utf-8").strip()
    parts = text.split(DELIMITER)
    if len(parts) != 3 or parts[0] != HEADER_TAG:
        raise ValueError(f"Invalid HEADER: {text!r}")
    return HeaderInfo(filename=parts[1], filesize=int(parts[2]))


# ── UDP helpers ─────────────────────────────────────────────────────
def encode_progress(filename: str, percent: float) -> bytes:
    """Build a PROGRESS datagram."""
    msg = f"{PROGRESS_TAG}{DELIMITER}{filename}{DELIMITER}{percent:.1f}{LINE_END}"
    return msg.encode("utf-8")


@dataclass
class ProgressInfo:
    filename: str
    percent: float


def decode_progress(raw: bytes) -> ProgressInfo:
    """Parse a PROGRESS datagram received over UDP.

    Raises ValueError if the datagram is malformed.
    """
    text = raw.decode("utf-8").strip()
    parts = text.split(DELIMITER)
    if len(parts) != 3 or parts[0] != PROGRESS_TAG:
        raise ValueError(f"Invalid PROGRESS: {text!r}")
    return ProgressInfo(filename=parts[1], percent=float(parts[2]))


# ── Utility: length-prefixed framing for TCP control messages ───────
def send_msg(sock, data: bytes) -> None:
    """Send a length-prefixed message so the receiver knows where it ends."""
    length = struct.pack("!I", len(data))
    sock.sendall(length + data)


def recv_msg(sock) -> bytes | None:
    """Receive a length-prefixed message. Returns None on disconnect."""
    raw_len = _recv_exact(sock, 4)
    if raw_len is None:
        return None
    (length,) = struct.unpack("!I", raw_len)
    return _recv_exact(sock, length)


def _recv_exact(sock, n: int) -> bytes | None:
    """Read exactly *n* bytes from *sock*. Returns None on premature close."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)
