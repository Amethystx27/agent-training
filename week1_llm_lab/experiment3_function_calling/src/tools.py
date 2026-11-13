"""Local Python tools used by the experiment's Function Calling loop."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone as datetime_timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ToolResult = dict[str, Any]

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CONFERENCE_DATA: dict[str, dict[str, str]] = {
    "ICCBDA 2027": {
        "submission_deadline": "2027-02-15",
        "conference_start": "2027-05-21",
        "conference_end": "2027-05-23",
    }
}

_CONFERENCE_LOOKUP = {
    " ".join(name.split()).casefold(): name for name in CONFERENCE_DATA
}


class ToolInputError(ValueError):
    """An expected validation error that can be returned to the model."""

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


def _failure(error_code: str, message: str) -> ToolResult:
    return {
        "ok": False,
        "error_code": error_code,
        "error": message,
    }


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(
            "INVALID_ARGUMENT",
            f"{field_name} must be a non-empty string.",
        )
    return value.strip()


def _load_timezone(value: object, field_name: str = "timezone") -> ZoneInfo:
    timezone_name = _required_text(value, field_name)
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ToolInputError(
            "INVALID_TIMEZONE",
            f"Unknown IANA timezone: {timezone_name}",
        ) from exc


def get_current_time(timezone: str) -> ToolResult:
    """Return the current time in a specified IANA timezone."""

    try:
        timezone_name = _required_text(timezone, "timezone")
        zone = _load_timezone(timezone_name)
    except ToolInputError as exc:
        return _failure(exc.error_code, str(exc))

    now = datetime.now(zone).replace(microsecond=0)
    return {
        "ok": True,
        "timezone": timezone_name,
        "datetime": now.isoformat(),
        "formatted_time": now.strftime("%Y-%m-%d %H:%M:%S"),
    }


def days_until(
    target_date: str,
    *,
    today: date | None = None,
) -> ToolResult:
    """Calculate the number of calendar days from today to target_date."""

    try:
        target_text = _required_text(target_date, "target_date")
        if not _DATE_PATTERN.fullmatch(target_text):
            raise ValueError("Date must use YYYY-MM-DD format.")
        target = date.fromisoformat(target_text)
    except (ToolInputError, ValueError) as exc:
        return _failure("INVALID_DATE", f"Invalid target_date: {exc}")

    reference_date = today if today is not None else date.today()
    return {
        "ok": True,
        "target_date": target_text,
        "today": reference_date.isoformat(),
        "days_remaining": (target - reference_date).days,
    }


def get_conference_deadline(conference_name: str) -> ToolResult:
    """Look up a simulated conference deadline by normalized conference name."""

    try:
        requested_name = _required_text(conference_name, "conference_name")
    except ToolInputError as exc:
        return _failure(exc.error_code, str(exc))

    normalized_name = " ".join(requested_name.split()).casefold()
    canonical_name = _CONFERENCE_LOOKUP.get(normalized_name)
    if canonical_name is None:
        return _failure(
            "CONFERENCE_NOT_FOUND",
            f"Conference not found: {requested_name}",
        )

    return {
        "ok": True,
        "conference_name": canonical_name,
        **CONFERENCE_DATA[canonical_name],
    }


def convert_timezone(
    local_datetime: str,
    source_timezone: str,
    target_timezone: str,
) -> ToolResult:
    """Convert a local wall-clock time using timezone-aware arithmetic."""

    try:
        datetime_text = _required_text(local_datetime, "local_datetime")
        if "T" not in datetime_text and " " not in datetime_text:
            raise ToolInputError(
                "INVALID_DATETIME",
                "local_datetime must include both a date and a time.",
            )

        source_zone = _load_timezone(source_timezone, "source_timezone")
        target_zone = _load_timezone(target_timezone, "target_timezone")

        parsed = datetime.fromisoformat(datetime_text)
        if parsed.tzinfo is not None:
            raise ToolInputError(
                "INVALID_DATETIME",
                "local_datetime must not include an offset; use source_timezone.",
            )

        first_interpretation = parsed.replace(tzinfo=source_zone, fold=0)
        second_interpretation = parsed.replace(tzinfo=source_zone, fold=1)

        if first_interpretation.utcoffset() != second_interpretation.utcoffset():
            normalized_back = (
                first_interpretation.astimezone(datetime_timezone.utc)
                .astimezone(source_zone)
                .replace(tzinfo=None)
            )
            if normalized_back != parsed:
                raise ToolInputError(
                    "NON_EXISTENT_LOCAL_TIME",
                    f"{datetime_text} does not exist in {source_zone.key} "
                    "because of a daylight-saving transition.",
                )
            raise ToolInputError(
                "AMBIGUOUS_LOCAL_TIME",
                f"{datetime_text} is ambiguous in {source_zone.key}; "
                "please specify the UTC offset.",
            )

        converted = first_interpretation.astimezone(target_zone)
    except ToolInputError as exc:
        return _failure(exc.error_code, str(exc))
    except ValueError as exc:
        return _failure("INVALID_DATETIME", f"Invalid local_datetime: {exc}")

    return {
        "ok": True,
        "source_timezone": source_zone.key,
        "source_datetime": first_interpretation.isoformat(),
        "target_timezone": target_zone.key,
        "target_datetime": converted.isoformat(),
        "formatted_time": converted.strftime("%Y-%m-%d %H:%M:%S"),
        "formatted_time_with_timezone": converted.strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        ),
    }
