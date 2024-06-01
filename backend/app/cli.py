"""Operational commands: python -m app.cli <command>"""

import sys

from app.services import storage


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "init-storage":
        storage.ensure_bucket()
        print("bucket ready")
    else:
        print("usage: python -m app.cli init-storage", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main(sys.argv)
