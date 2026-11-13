"""Complete multi-round Function Calling loop for the basic experiment."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from call_logger import CallLogger
from config import AppConfig, load_config
from dispatcher import ToolDispatcher
from first_turn import REFERENCE_TIMEZONE, build_system_prompt
from tool_schemas import BASIC_TOOL_SCHEMAS


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Public result from one complete agent run."""

    ok: bool
    answer: str
    rounds: int
    tool_call_count: int
    log_path: str
    error_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "answer": self.answer,
            "rounds": self.rounds,
            "tool_call_count": self.tool_call_count,
            "log_path": self.log_path,
            "error_code": self.error_code,
        }


class FunctionCallingAgent:
    """Run model/tool rounds until the model returns a final answer."""

    def __init__(
        self,
        *,
        config: AppConfig | None = None,
        client: Any | None = None,
        dispatcher: ToolDispatcher | None = None,
        log_dir: Path | str | None = None,
        max_tool_rounds: int = 6,
    ) -> None:
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1.")

        self.config = config or load_config()
        self.client = client or self.config.create_openai_client()
        self.dispatcher = dispatcher or ToolDispatcher()
        self.log_dir = log_dir
        self.max_tool_rounds = max_tool_rounds

    def run(self, user_message: str) -> AgentResult:
        normalized_message = user_message.strip()
        if not normalized_message:
            raise ValueError("user_message must not be empty.")

        logger = CallLogger(
            normalized_message,
            self.config.model_name,
            log_dir=self.log_dir,
        )
        started = time.monotonic()
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": build_system_prompt(
                    datetime.now(ZoneInfo(REFERENCE_TIMEZONE))
                ),
            },
            {"role": "user", "content": normalized_message},
        ]
        tool_call_count = 0
        rounds = 0

        try:
            for round_number in range(1, self.max_tool_rounds + 1):
                rounds = round_number
                logger.record(
                    "model_request",
                    round=round_number,
                    message_count=len(messages),
                )
                response = self.client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    tools=BASIC_TOOL_SCHEMAS,
                    tool_choice="auto",
                )
                if not response.choices:
                    raise RuntimeError("The model returned no choices.")

                choice = response.choices[0]
                message = choice.message
                tool_calls = list(message.tool_calls or [])
                logger.record(
                    "model_response",
                    round=round_number,
                    finish_reason=choice.finish_reason,
                    content=message.content or "",
                    tool_calls=[
                        {
                            "id": tool_call.id,
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        }
                        for tool_call in tool_calls
                    ],
                )

                if not tool_calls:
                    answer = message.content or ""
                    if not answer.strip():
                        return self._finish_failure(
                            logger,
                            started,
                            rounds,
                            tool_call_count,
                            "EMPTY_MODEL_RESPONSE",
                            "模型未返回最终回答。",
                        )
                    return self._finish_success(
                        logger,
                        started,
                        answer,
                        rounds,
                        tool_call_count,
                    )

                messages.append(self._assistant_tool_call_message(message))

                for tool_call in tool_calls:
                    tool_call_count += 1
                    call_started = time.monotonic()
                    result = self.dispatcher.dispatch(
                        tool_call.function.name,
                        tool_call.function.arguments,
                    )
                    duration_ms = round(
                        (time.monotonic() - call_started) * 1000,
                        2,
                    )
                    logger.record(
                        "tool_call",
                        round=round_number,
                        sequence=tool_call_count,
                        tool_call_id=tool_call.id,
                        tool_name=tool_call.function.name,
                        arguments=tool_call.function.arguments,
                        duration_ms=duration_ms,
                        status="success" if result.get("ok") else "error",
                        result=result,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )

            return self._finish_failure(
                logger,
                started,
                rounds,
                tool_call_count,
                "MAX_TOOL_ROUNDS",
                "工具调用轮数达到上限，未能生成最终回答。",
            )
        except Exception as exc:
            logger.record(
                "runtime_error",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return self._finish_failure(
                logger,
                started,
                rounds,
                tool_call_count,
                "AGENT_RUNTIME_ERROR",
                f"Agent 执行失败：{type(exc).__name__}",
            )

    @staticmethod
    def _assistant_tool_call_message(message: Any) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in message.tool_calls
            ],
        }

    def _finish_success(
        self,
        logger: CallLogger,
        started: float,
        answer: str,
        rounds: int,
        tool_call_count: int,
    ) -> AgentResult:
        logger.record(
            "run_end",
            status="success",
            rounds=rounds,
            tool_call_count=tool_call_count,
            final_answer=answer,
            duration_ms=round((time.monotonic() - started) * 1000, 2),
        )
        return AgentResult(
            ok=True,
            answer=answer,
            rounds=rounds,
            tool_call_count=tool_call_count,
            log_path=str(logger.path),
        )

    def _finish_failure(
        self,
        logger: CallLogger,
        started: float,
        rounds: int,
        tool_call_count: int,
        error_code: str,
        answer: str,
    ) -> AgentResult:
        logger.record(
            "run_end",
            status="error",
            error_code=error_code,
            rounds=rounds,
            tool_call_count=tool_call_count,
            final_answer=answer,
            duration_ms=round((time.monotonic() - started) * 1000, 2),
        )
        return AgentResult(
            ok=False,
            answer=answer,
            rounds=rounds,
            tool_call_count=tool_call_count,
            log_path=str(logger.path),
            error_code=error_code,
        )


def main() -> int:
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Run the complete basic Function Calling agent."
    )
    parser.add_argument("message", nargs="+", help="User message")
    parser.add_argument(
        "--log-dir",
        default=None,
        help="Optional log directory inside experiment3_function_calling.",
    )
    args = parser.parse_args()

    agent = FunctionCallingAgent(log_dir=args.log_dir)
    result = agent.run(" ".join(args.message))
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
