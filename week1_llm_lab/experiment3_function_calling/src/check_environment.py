"""Verify the local experiment environment without printing secrets."""

from __future__ import annotations

import sys
from zoneinfo import ZoneInfo

from config import DEFAULT_ENV_PATH, load_config


REQUIRED_TIMEZONES = (
    "Asia/Shanghai",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Europe/London",
    "America/New_York",
    "America/Los_Angeles",
)


def main() -> int:
    try:
        config = load_config()
        for timezone_name in REQUIRED_TIMEZONES:
            ZoneInfo(timezone_name)
    except Exception as exc:
        print(f"Environment check failed: {exc}", file=sys.stderr)
        return 1

    print("Environment check passed.")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Interpreter: {sys.executable}")
    print(f"Environment file: {DEFAULT_ENV_PATH}")
    print(f"Model: {config.model_name}")
    print(f"Timezone data: {len(REQUIRED_TIMEZONES)} zones loaded")
    print("OpenAI client: configured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
