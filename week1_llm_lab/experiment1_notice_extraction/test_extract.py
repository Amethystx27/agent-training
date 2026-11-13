"""Compatibility entry point. New work should use validate_schema.py."""

import sys

from validate_schema import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
