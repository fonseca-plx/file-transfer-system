"""gRPC file-transfer client — streams a file to the Go server."""

import logging
import os
import sys
from typing import Iterator

import grpc

# Generated stubs (run `make proto-py` first)
from pb import file_transfer_pb2 as pb
from pb import file_transfer_pb2_grpc as pb_grpc

# ── Constants ───────────────────────────────────────────────────────────────
CHUNK_SIZE = 4096  # 4 KB — matches the sockets version
SERVER_ADDR = "localhost:50051"
PROGRESS_INTERVAL = 5  # report every N chunks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)
log = logging.getLogger(__name__)


# ── Chunk generator ────────────────────────────────────────────────────────
def _chunk_iterator(filepath: str) -> Iterator[pb.Chunk]:
    """Yield Chunk messages: metadata first, then data chunks."""
    filename = os.path.basename(filepath)
    file_size = os.path.getsize(filepath)

    # First message: metadata
    yield pb.Chunk(
        metadata=pb.FileMetadata(filename=filename, file_size=file_size)
    )
    log.info("[gRPC] Sending metadata — file=%s size=%d", filename, file_size)

    bytes_sent = 0
    chunk_count = 0

    with open(filepath, "rb") as f:
        while True:
            data = f.read(CHUNK_SIZE)
            if not data:
                break
            yield pb.Chunk(data=data)
            bytes_sent += len(data)
            chunk_count += 1

            if chunk_count % PROGRESS_INTERVAL == 0 and file_size > 0:
                pct = bytes_sent / file_size * 100
                log.info(
                    "[SEND] %s — %.1f%% (%d/%d bytes)",
                    filename,
                    pct,
                    bytes_sent,
                    file_size,
                )

    log.info(
        "[SEND] Finished streaming: %s — %d bytes in %d chunks",
        filename,
        bytes_sent,
        chunk_count,
    )


# ── Upload function ────────────────────────────────────────────────────────
def upload(filepath: str) -> None:
    """Connect to the gRPC server and upload a file."""
    if not os.path.isfile(filepath):
        log.error("[gRPC] File not found: %s", filepath)
        sys.exit(1)

    log.info("[gRPC] Connecting to %s", SERVER_ADDR)
    channel = grpc.insecure_channel(SERVER_ADDR)
    stub = pb_grpc.FileTransferStub(channel)

    try:
        response = stub.Upload(_chunk_iterator(filepath))
        log.info(
            "[gRPC] Server response — file=%s bytes_received=%d message='%s'",
            response.filename,
            response.bytes_received,
            response.message,
        )
    except grpc.RpcError as e:
        log.error("[gRPC] RPC failed: %s — %s", e.code(), e.details())
        sys.exit(1)
    finally:
        channel.close()

    log.info("[SEND] Transfer complete: %s", os.path.basename(filepath))


# ── CLI entry-point ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <filepath>")
        sys.exit(1)

    upload(sys.argv[1])
