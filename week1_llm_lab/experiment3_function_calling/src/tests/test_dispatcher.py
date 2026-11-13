"""Tests for tool schemas and the allowlist dispatcher."""

from __future__ import annotations

import unittest

from dispatcher import ToolDispatcher
from tool_schemas import BASIC_TOOL_SCHEMAS


class DispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dispatcher = ToolDispatcher()

    def test_schema_names_match_dispatcher_allowlist(self) -> None:
        schema_names = {
            schema["function"]["name"] for schema in BASIC_TOOL_SCHEMAS
        }

        self.assertEqual(schema_names, set(self.dispatcher.tool_names))
        self.assertEqual(len(schema_names), 4)

    def test_dispatch_known_tool_with_json_arguments(self) -> None:
        result = self.dispatcher.dispatch(
            "get_conference_deadline",
            '{"conference_name": "ICCBDA 2027"}',
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["submission_deadline"], "2027-02-15")

    def test_dispatch_known_tool_with_mapping_arguments(self) -> None:
        result = self.dispatcher.dispatch(
            "get_current_time",
            {"timezone": "Asia/Singapore"},
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["timezone"], "Asia/Singapore")

    def test_dispatch_rejects_unknown_tool(self) -> None:
        result = self.dispatcher.dispatch("execute_code", "{}")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "UNKNOWN_TOOL")

    def test_dispatch_rejects_invalid_json(self) -> None:
        result = self.dispatcher.dispatch("days_until", "{not-json}")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_JSON")

    def test_dispatch_rejects_non_object_json(self) -> None:
        result = self.dispatcher.dispatch("days_until", '["2027-02-15"]')

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_ARGUMENTS")

    def test_dispatch_rejects_missing_argument(self) -> None:
        result = self.dispatcher.dispatch("days_until", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_ARGUMENTS")

    def test_dispatch_rejects_wrong_argument_type(self) -> None:
        result = self.dispatcher.dispatch("days_until", {"target_date": 20270215})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_ARGUMENTS")

    def test_dispatch_rejects_unexpected_argument(self) -> None:
        result = self.dispatcher.dispatch(
            "get_current_time",
            {"timezone": "Asia/Tokyo", "command": "whoami"},
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "INVALID_ARGUMENTS")


if __name__ == "__main__":
    unittest.main()
