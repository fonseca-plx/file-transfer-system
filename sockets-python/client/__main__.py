"""
client/__main__.py — CLI entry point for the file-upload client.

Usage::

    cd sockets-python/
    python -m client <filepath>
"""

from __future__ import annotations

import logging
import sys

from client.sender import send_file


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python -m client <filepath>")
        sys.exit(1)

    send_file(sys.argv[1])


if __name__ == "__main__":
    main()
