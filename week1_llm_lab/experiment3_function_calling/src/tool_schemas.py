"""Function declarations sent to the model for the basic experiment."""

from __future__ import annotations

from typing import Any


GET_CURRENT_TIME_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "查询指定 IANA 时区的当前日期和时间。",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": (
                        "IANA 时区名称，例如 Asia/Singapore、"
                        "America/New_York。"
                    ),
                }
            },
            "required": ["timezone"],
            "additionalProperties": False,
        },
    },
}


DAYS_UNTIL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "days_until",
        "description": "计算从今天到指定日期相差的日历天数。",
        "parameters": {
            "type": "object",
            "properties": {
                "target_date": {
                    "type": "string",
                    "description": "目标日期，必须使用 YYYY-MM-DD 格式。",
                }
            },
            "required": ["target_date"],
            "additionalProperties": False,
        },
    },
}


GET_CONFERENCE_DEADLINE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_conference_deadline",
        "description": "根据会议名称查询模拟会议数据中的投稿截止日期。",
        "parameters": {
            "type": "object",
            "properties": {
                "conference_name": {
                    "type": "string",
                    "description": "完整会议名称，例如 ICCBDA 2027。",
                }
            },
            "required": ["conference_name"],
            "additionalProperties": False,
        },
    },
}


CONVERT_TIMEZONE_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "convert_timezone",
        "description": (
            "将来源时区的本地日期时间转换为目标时区时间，"
            "自动处理时区偏移和夏令时。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "local_datetime": {
                    "type": "string",
                    "description": (
                        "来源时区的本地日期时间，例如 "
                        "2027-02-15T09:00:00；不要包含 UTC 偏移。"
                    ),
                },
                "source_timezone": {
                    "type": "string",
                    "description": "来源 IANA 时区，例如 Asia/Tokyo。",
                },
                "target_timezone": {
                    "type": "string",
                    "description": "目标 IANA 时区，例如 Asia/Shanghai。",
                },
            },
            "required": [
                "local_datetime",
                "source_timezone",
                "target_timezone",
            ],
            "additionalProperties": False,
        },
    },
}


BASIC_TOOL_SCHEMAS: list[dict[str, Any]] = [
    GET_CURRENT_TIME_SCHEMA,
    DAYS_UNTIL_SCHEMA,
    GET_CONFERENCE_DEADLINE_SCHEMA,
    CONVERT_TIMEZONE_SCHEMA,
]
