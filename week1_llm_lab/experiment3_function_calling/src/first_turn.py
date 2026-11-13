"""Make the first model request and surface any requested tool calls."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from config import AppConfig, load_config
from tool_schemas import BASIC_TOOL_SCHEMAS


REFERENCE_TIMEZONE = "Asia/Shanghai"


def build_system_prompt(reference_datetime: datetime) -> str:
    """Build a deterministic prompt with the current reference date."""

    current_date = reference_datetime.date().isoformat()
    return f"""
你是一个会议和时间助手。今天是 {current_date}，用户默认参考时区是
{REFERENCE_TIMEZONE}。

规则：
1. 查询准确当前时间、日期差值、会议截止日期或进行时区转换时，必须调用工具。
2. 不得编造会议信息。工具返回错误时，最终回答必须如实说明。
3. 未明确指定关键城市、日期或会议名称时，应先询问用户。
4. 只能使用提供的工具，不得假设工具已经执行。
5. 用户可以使用中文或英文提问。
""".strip()


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    """A tool request exactly as returned by the model."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class FirstTurnResult:
    """Safe, structured view of the first assistant response."""

    content: str | None
    finish_reason: str | None
    tool_calls: tuple[ToolCallRequest, ...]
    assistant_message: dict[str, Any]


def request_first_turn(
    user_message: str,
    *,
    config: AppConfig | None = None,
) -> FirstTurnResult:
    """Call the configured model once, without executing any tool."""

    normalized_message = user_message.strip()
    if not normalized_message:
        raise ValueError("user_message must not be empty.")

    active_config = config or load_config()
    now = datetime.now(ZoneInfo(REFERENCE_TIMEZONE))
    client = active_config.create_openai_client()

    response = client.chat.completions.create(
        model=active_config.model_name,
        messages=[
            {"role": "system", "content": build_system_prompt(now)},
            {"role": "user", "content": normalized_message},
        ],
        tools=BASIC_TOOL_SCHEMAS,
        tool_choice="auto",
    )
    if not response.choices:
        raise RuntimeError("The model returned no choices.")

    choice = response.choices[0]
    message = choice.message
    tool_calls = tuple(
        ToolCallRequest(
            id=tool_call.id,
            name=tool_call.function.name,
            arguments=tool_call.function.arguments,
        )
        for tool_call in (message.tool_calls or [])
    )

    return FirstTurnResult(
        content=message.content,
        finish_reason=choice.finish_reason,
        tool_calls=tool_calls,
        assistant_message=message.model_dump(exclude_none=True, mode="json"),
    )


def result_as_dict(result: FirstTurnResult) -> dict[str, Any]:
    """Convert the first-turn result to a printable, JSON-safe structure."""

    return {
        "content": result.content,
        "finish_reason": result.finish_reason,
        "tool_calls": [
            {
                "id": tool_call.id,
                "name": tool_call.name,
                "arguments": tool_call.arguments,
            }
            for tool_call in result.tool_calls
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Make one model call and show the first-turn tool requests."
    )
    parser.add_argument("message", nargs="+", help="User message")
    args = parser.parse_args()

    result = request_first_turn(" ".join(args.message))
    print(json.dumps(result_as_dict(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
