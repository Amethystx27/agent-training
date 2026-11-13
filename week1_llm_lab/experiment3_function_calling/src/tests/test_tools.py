"""Unit tests for the local, model-independent experiment tools."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta

from tools import (
    convert_timezone,
    days_until,
    get_conference_deadline,
    get_current_time,
)


class TimeToolTests(unittest.TestCase):
    def test_get_current_time_returns_aware_datetime(self) -> None:
        result = get_current_time("Asia/Singapore")

        self.assertTrue(result["ok"])
        self.assertEqual(result["timezone"], "Asia/Singapore")
        parsed = datetime.fromisoformat(result["datetime"])
        self.assertIsNotNone(parsed.utcoffset())
        self.assertLess(abs(datetime.now(parsed.tzinfo) - parsed), timedelta(seconds=5))

    def test_get_current_time_rejects_unknown_timezone(self) -> None:
        result = get_current_time("Mars/Olympus_Mons")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_TIMEZONE")

    def test_convert_tokyo_to_beijing(self) -> None:
        result = convert_timezone(
            "2026-11-14T09:00:00",
            "Asia/Tokyo",
            "Asia/Shanghai",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            datetime.fromisoformat(result["target_datetime"]),
            datetime.fromisoformat("2026-11-14T08:00:00+08:00"),
        )

    def test_convert_rejects_aware_input(self) -> None:
        result = convert_timezone(
            "2026-11-14T09:00:00+09:00",
            "Asia/Tokyo",
            "Asia/Shanghai",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_DATETIME")

    def test_convert_rejects_nonexistent_dst_time(self) -> None:
        result = convert_timezone(
            "2026-03-08T02:30:00",
            "America/New_York",
            "UTC",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "NON_EXISTENT_LOCAL_TIME")

    def test_convert_rejects_ambiguous_dst_time(self) -> None:
        result = convert_timezone(
            "2026-11-01T01:30:00",
            "America/New_York",
            "UTC",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "AMBIGUOUS_LOCAL_TIME")


class DateToolTests(unittest.TestCase):
    def test_days_until_uses_injected_reference_date(self) -> None:
        result = days_until("2027-02-15", today=date(2026, 11, 13))

        self.assertTrue(result["ok"])
        self.assertEqual(result["today"], "2026-11-13")
        self.assertEqual(result["days_remaining"], 94)

    def test_days_until_rejects_invalid_calendar_date(self) -> None:
        result = days_until("2027-02-30")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_DATE")

    def test_days_until_rejects_non_iso_format(self) -> None:
        result = days_until("15/02/2027")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_DATE")


class ConferenceToolTests(unittest.TestCase):
    def test_conference_lookup_is_case_and_space_insensitive(self) -> None:
        result = get_conference_deadline("  iccbda   2027 ")

        self.assertTrue(result["ok"])
        self.assertEqual(result["conference_name"], "ICCBDA 2027")
        self.assertEqual(result["submission_deadline"], "2027-02-15")

    def test_unknown_conference_returns_structured_error(self) -> None:
        result = get_conference_deadline("XYZ 2027")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "CONFERENCE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
