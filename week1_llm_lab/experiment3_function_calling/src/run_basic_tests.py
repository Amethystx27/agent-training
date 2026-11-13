"""Run and verify the six basic experiment scenarios end to end."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from agent import AgentResult, FunctionCallingAgent
from config import EXPERIMENT_DIR


REFERENCE_ZONE = ZoneInfo("Asia/Shanghai")
RESULTS_PATH = EXPERIMENT_DIR / "results" / "basic_test_results.json"
LOG_DIR = EXPERIMENT_DIR / "logs" / "basic"

Validation = Callable[[AgentResult, list[dict[str, Any]]], tuple[bool, list[str]]]


@dataclass(frozen=True, slots=True)
class BasicCase:
    number: str
    question: str
    validate: Validation


def load_events(log_path: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(log_path).read_text(encoding="utf-8").splitlines()
    ]


def tool_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event["event"] == "tool_call"]


def require_tool(
    events: list[dict[str, Any]],
    tool_name: str,
) -> dict[str, Any] | None:
    return next(
        (
            event
            for event in tool_events(events)
            if event["tool_name"] == tool_name
        ),
        None,
    )


def validate_current_time(
    result: AgentResult,
    events: list[dict[str, Any]],
    timezone_name: str,
) -> tuple[bool, list[str]]:
    checks: list[str] = []
    event = require_tool(events, "get_current_time")
    checks.append(f"调用 get_current_time: {event is not None}")
    ok = result.ok and event is not None and event["status"] == "success"
    if event is not None:
        value = event["result"]
        timezone_ok = value.get("timezone") == timezone_name
        checks.append(f"时区为 {timezone_name}: {timezone_ok}")
        ok = ok and timezone_ok
    checks.append(f"生成最终回答: {bool(result.answer.strip())}")
    return ok and bool(result.answer.strip()), checks


def validate_days_until(
    result: AgentResult,
    events: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    checks: list[str] = []
    event = require_tool(events, "days_until")
    checks.append(f"调用 days_until: {event is not None}")
    expected_days = (date(2027, 2, 15) - date.today()).days
    ok = result.ok and event is not None and event["status"] == "success"
    if event is not None:
        value = event["result"]
        date_ok = value.get("target_date") == "2027-02-15"
        days_ok = value.get("days_remaining") == expected_days
        checks.append(f"目标日期为 2027-02-15: {date_ok}")
        checks.append(f"剩余天数为 {expected_days}: {days_ok}")
        ok = ok and date_ok and days_ok
    checks.append(f"生成最终回答: {bool(result.answer.strip())}")
    return ok and bool(result.answer.strip()), checks


def validate_conference_chain(
    result: AgentResult,
    events: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    checks: list[str] = []
    conference_event = require_tool(events, "get_conference_deadline")
    days_event = require_tool(events, "days_until")
    checks.append(
        f"调用 get_conference_deadline: {conference_event is not None}"
    )
    checks.append(f"调用 days_until: {days_event is not None}")

    ok = result.ok and conference_event is not None and days_event is not None
    if conference_event is not None and days_event is not None:
        deadline = conference_event["result"].get("submission_deadline")
        checks.append(f"截止日期为 2027-02-15: {deadline == '2027-02-15'}")
        chained_date = days_event["result"].get("target_date")
        checks.append(f"日期参数来自会议结果: {chained_date == deadline}")
        ok = ok and deadline == "2027-02-15" and chained_date == deadline
    return ok, checks


def validate_timezone_conversion(
    result: AgentResult,
    events: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    checks: list[str] = []
    event = require_tool(events, "convert_timezone")
    checks.append(f"调用 convert_timezone: {event is not None}")
    ok = result.ok and event is not None and event["status"] == "success"
    if event is not None:
        value = event["result"]
        tomorrow = datetime.now(REFERENCE_ZONE).date() + timedelta(days=1)
        expected = datetime.combine(tomorrow, datetime.min.time()).replace(
            hour=8,
            tzinfo=REFERENCE_ZONE,
        )
        actual_text = value.get("target_datetime")
        actual = datetime.fromisoformat(actual_text) if actual_text else None
        target_ok = actual == expected
        checks.append(
            f"东京 09:00 对应北京 {expected.isoformat()}: {target_ok}"
        )
        ok = ok and target_ok
    return ok, checks


def validate_unknown_conference(
    result: AgentResult,
    events: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    checks: list[str] = []
    event = require_tool(events, "get_conference_deadline")
    checks.append(
        f"调用 get_conference_deadline: {event is not None}"
    )
    error_ok = (
        event is not None
        and event["status"] == "error"
        and event["result"].get("error_code") == "CONFERENCE_NOT_FOUND"
    )
    checks.append(f"返回 CONFERENCE_NOT_FOUND: {error_ok}")
    final_ok = result.ok and bool(result.answer.strip())
    checks.append(f"如实生成失败说明: {final_ok}")
    return error_ok and final_ok, checks


BASIC_CASES = (
    BasicCase(
        "Q1",
        "现在新加坡几点？",
        lambda result, events: validate_current_time(
            result, events, "Asia/Singapore"
        ),
    ),
    BasicCase(
        "Q2",
        "现在纽约几点？",
        lambda result, events: validate_current_time(
            result, events, "America/New_York"
        ),
    ),
    BasicCase(
        "Q3",
        "2027年2月15日距离今天还有多少天？",
        validate_days_until,
    ),
    BasicCase(
        "Q4",
        "ICCBDA 2027 的截稿日期还有多久？",
        validate_conference_chain,
    ),
    BasicCase(
        "Q5",
        "东京明天上午9点对应北京时间几点？",
        validate_timezone_conversion,
    ),
    BasicCase(
        "Q6",
        "查询不存在的会议 XYZ 2027 的截稿日期。",
        validate_unknown_conference,
    ),
)


def main() -> int:
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8")

    agent = FunctionCallingAgent(log_dir=LOG_DIR)
    summaries: list[dict[str, Any]] = []

    for case in BASIC_CASES:
        result = agent.run(case.question)
        events = load_events(result.log_path)
        passed, checks = case.validate(result, events)
        summary = {
            "number": case.number,
            "question": case.question,
            "passed": passed,
            "checks": checks,
            "answer": result.answer,
            "rounds": result.rounds,
            "tool_call_count": result.tool_call_count,
            "agent_ok": result.ok,
            "error_code": result.error_code,
            "log_path": result.log_path,
        }
        summaries.append(summary)
        print(f"{case.number} {'PASS' if passed else 'FAIL'} {case.question}")

    report = {
        "run_at": datetime.now(REFERENCE_ZONE).isoformat(),
        "passed": sum(item["passed"] for item in summaries),
        "total": len(summaries),
        "cases": summaries,
    }
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Results: {RESULTS_PATH}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
