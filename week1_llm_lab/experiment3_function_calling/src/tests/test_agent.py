"""Unit tests for the complete Function Calling loop using a fake model."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent import FunctionCallingAgent
from config import EXPERIMENT_DIR, AppConfig


def make_tool_response(tool_calls: list[tuple[str, str, dict]]) -> SimpleNamespace:
    message_tool_calls = [
        SimpleNamespace(
            id=call_id,
            function=SimpleNamespace(
                name=name,
                arguments=json.dumps(arguments, ensure_ascii=False),
            ),
        )
        for call_id, name, arguments in tool_calls
    ]
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=message_tool_calls,
                ),
                finish_reason="tool_calls",
            )
        ]
    )


def make_final_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=None),
                finish_reason="stop",
            )
        ]
    )


class FakeCompletions:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.responses = responses
        self.requests: list[dict] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.requests.append(copy.deepcopy(kwargs))
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class AgentLoopTests(unittest.TestCase):
    def test_agent_runs_two_tool_rounds_then_returns_answer(self) -> None:
        responses = [
            make_tool_response(
                [
                    (
                        "call_1",
                        "get_conference_deadline",
                        {"conference_name": "ICCBDA 2027"},
                    )
                ]
            ),
            make_tool_response(
                [
                    (
                        "call_2",
                        "days_until",
                        {"target_date": "2027-02-15"},
                    )
                ]
            ),
            make_final_response("ICCBDA 2027 的截稿日期是 2027-02-15。"),
        ]
        client = FakeClient(responses)
        config = AppConfig(
            api_key="test-only",
            base_url="http://localhost/v1",
            model_name="fake-model",
        )

        with tempfile.TemporaryDirectory(dir=EXPERIMENT_DIR) as log_dir:
            agent = FunctionCallingAgent(
                config=config,
                client=client,
                log_dir=Path(log_dir),
            )
            result = agent.run("ICCBDA 2027 的截稿日期还有多久？")

            self.assertTrue(result.ok)
            self.assertEqual(result.rounds, 3)
            self.assertEqual(result.tool_call_count, 2)
            self.assertIn("2027-02-15", result.answer)

            requests = client.chat.completions.requests
            self.assertEqual(len(requests), 3)
            self.assertEqual(
                requests[1]["messages"][-1]["role"],
                "tool",
            )
            self.assertEqual(
                requests[1]["messages"][-1]["tool_call_id"],
                "call_1",
            )
            self.assertEqual(
                requests[2]["messages"][-1]["tool_call_id"],
                "call_2",
            )

            log_events = [
                json.loads(line)
                for line in Path(result.log_path).read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            event_types = [event["event"] for event in log_events]
            self.assertEqual(event_types[0], "run_start")
            self.assertEqual(event_types[-1], "run_end")
            self.assertEqual(event_types.count("tool_call"), 2)
            tool_events = [
                event for event in log_events if event["event"] == "tool_call"
            ]
            self.assertEqual(tool_events[0]["sequence"], 1)
            self.assertEqual(tool_events[1]["sequence"], 2)
            self.assertTrue(all(event["status"] == "success" for event in tool_events))

    def test_unknown_tool_result_is_returned_to_model(self) -> None:
        responses = [
            make_tool_response(
                [("call_bad", "execute_code", {"code": "print('unsafe')"})]
            ),
            make_final_response("无法执行该工具。"),
        ]
        client = FakeClient(responses)
        config = AppConfig(
            api_key="test-only",
            base_url="http://localhost/v1",
            model_name="fake-model",
        )

        with tempfile.TemporaryDirectory(dir=EXPERIMENT_DIR) as log_dir:
            result = FunctionCallingAgent(
                config=config,
                client=client,
                log_dir=Path(log_dir),
            ).run("执行任意代码")

            self.assertTrue(result.ok)
            tool_message = client.chat.completions.requests[1]["messages"][-1]
            tool_result = json.loads(tool_message["content"])
            self.assertFalse(tool_result["ok"])
            self.assertEqual(tool_result["error_code"], "UNKNOWN_TOOL")

    def test_log_directory_outside_experiment_is_rejected(self) -> None:
        config = AppConfig(
            api_key="test-only",
            base_url="http://localhost/v1",
            model_name="fake-model",
        )

        with self.assertRaisesRegex(
            ValueError,
            "experiment3_function_calling",
        ):
            FunctionCallingAgent(
                config=config,
                client=FakeClient([]),
                log_dir=EXPERIMENT_DIR.parent,
            ).run("测试日志目录限制")


if __name__ == "__main__":
    unittest.main()
