"""
实验3：会议时间查询工具（Function Calling）
=========================================
基础实验（不含进阶挑战）：
  1. 实现 4 个 Python 工具：get_current_time / days_until /
     get_conference_deadline / convert_timezone
  2. 模型根据用户自然语言选择工具 -> 程序执行 -> 结果回传 -> 模型组织答案
  3. 覆盖测试问题 Q1–Q6
  4. 白名单执行（禁止 eval / 任意代码执行）、参数与异常校验

运行：
  # 真实调用 API（需要 .env 配置）
  python main.py --all
  python main.py --question "现在新加坡几点？"

  # 离线演示（不依赖网络）
  python main.py --all --mock

  # 单独验证 4 个工具能否正确返回
  python main.py --selftest
"""
import os
import json
import argparse
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from openai import OpenAI

# ----------------------------------------------------------------------------
# 1. 加载配置
# ----------------------------------------------------------------------------
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
API_KEY = os.getenv("API_KEY")
API_BASE = os.getenv("API_BASE")
MODEL = os.getenv("MODEL", "deepseek-flash")
client = OpenAI(api_key=API_KEY, base_url=API_BASE) if API_KEY else None

TODAY = date.today()


# ----------------------------------------------------------------------------
# 2. Python 工具实现
# ----------------------------------------------------------------------------
def get_current_time(timezone: str) -> dict:
    """工具1：查询指定 IANA 时区的当前时间。"""
    try:
        tz = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return {"error": f"无效时区: {timezone}"}
    now = datetime.now(tz)
    return {
        "timezone": timezone,
        "datetime": now.isoformat(),
        "formatted_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


def days_until(target_date: str) -> dict:
    """工具2：计算目标日期距离今天还有多少天。"""
    try:
        target = date.fromisoformat(target_date)
    except ValueError:
        return {"error": f"无效日期: {target_date}，应为 YYYY-MM-DD"}
    return {
        "target_date": target_date,
        "today": TODAY.isoformat(),
        "days_remaining": (target - TODAY).days,
    }


# 模拟会议数据库（基础实验：字典实现）
CONFERENCE_DATA = {
    "ICCBDA 2027": {
        "submission_deadline": "2027-02-15",
        "conference_start": "2027-05-21",
        "conference_end": "2027-05-23",
    }
}


def get_conference_deadline(conference_name: str) -> dict:
    """工具3：查询模拟会议数据。"""
    result = CONFERENCE_DATA.get(conference_name)
    if result is None:
        return {"error": "Conference not found", "conference_name": conference_name}
    return {"conference_name": conference_name, **result}


def convert_timezone(datetime_str: str, source_timezone: str, target_timezone: str) -> dict:
    """工具4：将带日期时间从源时区转换到目标时区（自动处理夏令时）。"""
    try:
        src_tz = ZoneInfo(source_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return {"error": f"无效源时区: {source_timezone}"}
    try:
        tgt_tz = ZoneInfo(target_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return {"error": f"无效目标时区: {target_timezone}"}

    s = datetime_str.strip().lower()
    s = s.replace("tomorrow", (TODAY + timedelta(days=1)).isoformat())
    s = s.replace("today", TODAY.isoformat())
    s = s.replace("t", " ").replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            naive = datetime.strptime(s, fmt)
            break
        except ValueError:
            continue
    else:
        return {"error": f"无法解析时间: {datetime_str}，应为 YYYY-MM-DD HH:MM"}

    src = naive.replace(tzinfo=src_tz)
    tgt = src.astimezone(tgt_tz)
    return {
        "source": {"timezone": source_timezone, "datetime": src.isoformat()},
        "target": {
            "timezone": target_timezone,
            "datetime": tgt.isoformat(),
            "formatted_time": tgt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        },
        "offset_hours": round(
            (tgt.utcoffset().total_seconds() - src.utcoffset().total_seconds()) / 3600, 2
        ),
    }


# 白名单映射（唯一允许执行的工具）
FUNCTIONS = {
    "get_current_time": get_current_time,
    "days_until": days_until,
    "get_conference_deadline": get_conference_deadline,
    "convert_timezone": convert_timezone,
}


def execute_tool(name: str, args: dict) -> dict:
    if name not in FUNCTIONS:
        return {"error": f"未知工具: {name}（已拒绝执行）"}
    try:
        return FUNCTIONS[name](**args)
    except TypeError as e:
        return {"error": f"参数错误: {e}"}
    except Exception as e:
        return {"error": f"工具执行失败: {type(e).__name__}: {e}"}


# ----------------------------------------------------------------------------
# 3. Function Calling 工具声明
# ----------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "查询指定 IANA 时区的当前时间",
            "parameters": {
                "type": "object",
                "properties": {"timezone": {"type": "string", "description": "例如 Asia/Singapore"}},
                "required": ["timezone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "days_until",
            "description": "计算距离指定日期还有多少天",
            "parameters": {
                "type": "object",
                "properties": {"target_date": {"type": "string", "description": "YYYY-MM-DD"}},
                "required": ["target_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_conference_deadline",
            "description": "查询模拟会议数据库的投稿截止日期与举办日期",
            "parameters": {
                "type": "object",
                "properties": {"conference_name": {"type": "string", "description": "例如 ICCBDA 2027"}},
                "required": ["conference_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_timezone",
            "description": "将指定日期时间从源时区转换到目标时区，自动处理夏令时",
            "parameters": {
                "type": "object",
                "properties": {
                    "datetime_str": {"type": "string", "description": "源时区本地时间，YYYY-MM-DD HH:MM，可用 tomorrow/today"},
                    "source_timezone": {"type": "string", "description": "例如 Asia/Tokyo"},
                    "target_timezone": {"type": "string", "description": "例如 Asia/Shanghai"},
                },
                "required": ["datetime_str", "source_timezone", "target_timezone"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "你是一个会议时间查询助手。当用户提出时间、日期或时区相关问题时，"
    "请优先调用合适的工具来获取真实数据，再组织自然语言回答。"
    f"今天的日期是 {TODAY.isoformat()}。"
    "如果信息不足（例如用户未指定城市或日期），请先向用户澄清，不要猜测。"
    "最终回答中的天数、时间必须由工具运行结果得出。"
)


# ----------------------------------------------------------------------------
# 4. Agent 主循环（真实 API）
# ----------------------------------------------------------------------------
def run_agent(question: str, max_iter: int = 5) -> dict:
    if client is None:
        raise RuntimeError("未配置 API（缺少 API_KEY / API_BASE），请使用 --mock 模式。")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    logs = []
    for _ in range(max_iter):
        resp = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto")
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return {"answer": msg.content, "logs": logs}
        messages.append(msg)
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result = execute_tool(name, args)
            logs.append({"tool": name, "args": args, "result": result})
            messages.append(
                {"role": "tool", "content": json.dumps(result, ensure_ascii=False), "tool_call_id": tc.id}
            )
    return {"answer": "(模型在限定步数内未返回最终答案)", "logs": logs}


# ----------------------------------------------------------------------------
# 5. 离线 Mock（按 Q1–Q6 预设工具调用，演示闭环）
# ----------------------------------------------------------------------------
def mock_agent(question: str) -> dict:
    logs = []
    q = question.strip()

    if "新加坡" in q and "纽约" not in q and "几点" in q:
        r = get_current_time("Asia/Singapore"); logs.append({"tool": "get_current_time", "args": {"timezone": "Asia/Singapore"}, "result": r})
        answer = f"新加坡现在是 {r['formatted_time']}（{r['timezone']}）。"
    elif "纽约" in q and "新加坡" not in q and "几点" in q:
        r = get_current_time("America/New_York"); logs.append({"tool": "get_current_time", "args": {"timezone": "America/New_York"}, "result": r})
        answer = f"纽约现在是 {r['formatted_time']}（{r['timezone']}）。"
    elif "2027年2月15日" in q or ("2月15日" in q and "2027" in q):
        r = days_until("2027-02-15"); logs.append({"tool": "days_until", "args": {"target_date": "2027-02-15"}, "result": r})
        answer = f"2027-02-15 距离今天（{r['today']}）还有 {r['days_remaining']} 天。"
    elif "截稿" in q and "ICCBDA" in q:
        d = get_conference_deadline("ICCBDA 2027"); logs.append({"tool": "get_conference_deadline", "args": {"conference_name": "ICCBDA 2027"}, "result": d})
        dl = d["submission_deadline"]
        r = days_until(dl); logs.append({"tool": "days_until", "args": {"target_date": dl}, "result": r})
        answer = f"ICCBDA 2027 的投稿截止日期是 {dl}，距离今天还有 {r['days_remaining']} 天。"
    elif "东京" in q and "北京" in q:
        dt = (TODAY + timedelta(days=1)).isoformat() + " 09:00"
        r = convert_timezone(dt, "Asia/Tokyo", "Asia/Shanghai")
        logs.append({"tool": "convert_timezone", "args": {"datetime_str": dt, "source_timezone": "Asia/Tokyo", "target_timezone": "Asia/Shanghai"}, "result": r})
        answer = f"东京明天（{dt}）上午 9:00 对应北京时间为 {r['target']['formatted_time']}。"
    elif "XYZ" in q or "不存在" in q:
        d = get_conference_deadline("XYZ 2027"); logs.append({"tool": "get_conference_deadline", "args": {"conference_name": "XYZ 2027"}, "result": d})
        answer = "未找到名为「XYZ 2027」的会议，无法提供截稿日期。"
    else:
        answer = "（mock 模式未匹配到预置问题，请使用真实 API 或补充预置规则）"
    return {"answer": answer, "logs": logs}


# ----------------------------------------------------------------------------
# 6. 独立工具自检
# ----------------------------------------------------------------------------
def selftest():
    cases = [
        ("get_current_time", lambda: get_current_time("Asia/Shanghai")),
        ("days_until", lambda: days_until("2027-02-15")),
        ("get_conference_deadline", lambda: get_conference_deadline("ICCBDA 2027")),
        ("convert_timezone", lambda: convert_timezone((TODAY + timedelta(days=1)).isoformat() + " 09:00", "Asia/Tokyo", "Asia/Shanghai")),
        ("get_conference_deadline(notfound)", lambda: get_conference_deadline("XYZ 2027")),
    ]
    for name, fn in cases:
        try:
            print(f"[{name}] -> {json.dumps(fn(), ensure_ascii=False)}")
        except Exception as e:
            print(f"[{name}] ERROR: {e}")


# ----------------------------------------------------------------------------
# 7. 命令行入口
# ----------------------------------------------------------------------------
TEST_QUESTIONS = {
    "Q1": "现在新加坡几点？",
    "Q2": "现在纽约几点？",
    "Q3": "2027年2月15日距离今天还有多少天？",
    "Q4": "ICCBDA 2027 的截稿日期还有多久？",
    "Q5": "东京明天上午9点对应北京时间几点？",
    "Q6": "查询不存在的会议 XYZ 2027 的截稿日期。",
}


def main():
    parser = argparse.ArgumentParser(description="实验3：会议时间查询工具（Function Calling）")
    parser.add_argument("--question", help="单个自然语言问题")
    parser.add_argument("--all", action="store_true", help="运行 Q1–Q6 全部测试问题")
    parser.add_argument("--mock", action="store_true", help="离线演示模式")
    parser.add_argument("--selftest", action="store_true", help="独立运行 4 个工具验证返回")
    args = parser.parse_args()

    if args.selftest:
        selftest()
        return

    use_mock = args.mock or client is None
    results = []

    def run_one(qid, q):
        out = mock_agent(q) if use_mock else run_agent(q)
        results.append({"id": qid, "question": q, "answer": out["answer"], "tool_logs": out["logs"]})
        print(f"\n===== {qid} =====\n问题: {q}\n回答: {out['answer']}")
        for log in out["logs"]:
            print(f"  🔧 {log['tool']}({log['args']}) -> {json.dumps(log['result'], ensure_ascii=False)}")

    if args.question:
        run_one("Q?", args.question)
    elif args.all:
        for qid, q in TEST_QUESTIONS.items():
            run_one(qid, q)
    else:
        parser.print_help()
        return

    out = Path(__file__).resolve().parent / "results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 已保存 {len(results)} 条结果到 {out}")


if __name__ == "__main__":
    main()
