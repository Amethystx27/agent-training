"""Safely map model-requested tool calls to locally registered functions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Callable

from tool_schemas import BASIC_TOOL_SCHEMAS
from tools import (
    ToolResult,
    convert_timezone,
    days_until,
    get_conference_deadline,
    get_current_time,
)


ToolFunction = Callable[..., ToolResult]


class ToolDispatcher:
    """Resolve tool names from a fixed allowlist and validate their arguments."""

    def __init__(self) -> None:
        functions: dict[str, ToolFunction] = {
            "get_current_time": get_current_time,
            "days_until": days_until,
            "get_conference_deadline": get_conference_deadline,
            "convert_timezone": convert_timezone,
        }
        schemas = {
            schema["function"]["name"]: schema for schema in BASIC_TOOL_SCHEMAS
        }
        if functions.keys() != schemas.keys():
            raise RuntimeError("Tool schemas and registered functions do not match.")

        self._functions = functions
        self._parameters = {
            name: schema["function"]["parameters"]
            for name, schema in schemas.items()
        }

    @property
    def tool_names(self) -> tuple[str, ...]:
        """Return the fixed allowlist in a stable order."""

        return tuple(self._functions)

    def dispatch(
        self,
        tool_name: object,
        arguments: str | Mapping[str, Any] | None,
    ) -> ToolResult:
        """Parse, validate, and execute one model tool call."""

        if not isinstance(tool_name, str) or not tool_name:
            return self._failure(
                "INVALID_TOOL_NAME",
                "Tool name must be a non-empty string.",
            )

        function = self._functions.get(tool_name)
        if function is None:
            return self._failure(
                "UNKNOWN_TOOL",
                f"Tool is not registered: {tool_name}",
            )

        parsed_arguments = self._parse_arguments(arguments)
        if not parsed_arguments["ok"]:
            return parsed_arguments
        argument_values = parsed_arguments["arguments"]

        validation_error = self._validate_arguments(
            tool_name,
            argument_values,
        )
        if validation_error is not None:
            return validation_error

        try:
            result = function(**argument_values)
            json.dumps(result, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            return self._failure(
                "INVALID_ARGUMENTS",
                f"Invalid arguments for {tool_name}: {exc}",
            )
        except Exception:
            return self._failure(
                "TOOL_EXECUTION_ERROR",
                f"Tool execution failed: {tool_name}",
            )

        if not isinstance(result, dict):
            return self._failure(
                "INVALID_TOOL_RESULT",
                f"Tool did not return a JSON object: {tool_name}",
            )
        return result

    @staticmethod
    def _parse_arguments(
        arguments: str | Mapping[str, Any] | None,
    ) -> ToolResult:
        if arguments is None:
            return {"ok": True, "arguments": {}}
        if isinstance(arguments, Mapping):
            return {"ok": True, "arguments": dict(arguments)}
        if not isinstance(arguments, str):
            return ToolDispatcher._failure(
                "INVALID_ARGUMENTS",
                "Tool arguments must be a JSON object string.",
            )

        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            return ToolDispatcher._failure(
                "INVALID_JSON",
                f"Tool arguments are not valid JSON: {exc.msg}",
            )
        if not isinstance(parsed, dict):
            return ToolDispatcher._failure(
                "INVALID_ARGUMENTS",
                "Tool arguments must decode to a JSON object.",
            )
        return {"ok": True, "arguments": parsed}

    def _validate_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult | None:
        parameters = self._parameters[tool_name]
        properties = parameters.get("properties", {})
        required = parameters.get("required", [])

        missing = [name for name in required if name not in arguments]
        if missing:
            return self._failure(
                "INVALID_ARGUMENTS",
                f"Missing required arguments for {tool_name}: {', '.join(missing)}",
            )

        if parameters.get("additionalProperties") is False:
            unexpected = sorted(set(arguments) - set(properties))
            if unexpected:
                return self._failure(
                    "INVALID_ARGUMENTS",
                    f"Unexpected arguments for {tool_name}: {', '.join(unexpected)}",
                )

        for name, value in arguments.items():
            expected_type = properties[name].get("type")
            if expected_type == "string" and not isinstance(value, str):
                return self._failure(
                    "INVALID_ARGUMENTS",
                    f"Argument {name} for {tool_name} must be a string.",
                )
        return None

    @staticmethod
    def _failure(error_code: str, message: str) -> ToolResult:
        return {
            "ok": False,
            "error_code": error_code,
            "error": message,
        }
