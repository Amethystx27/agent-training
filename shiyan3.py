import json
import os
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from common import chat

# ================= 1. 模拟会议数据库 =================
conference_data = {
    "ICCBDA 2027": {
        "conference_name": "ICCBDA 2027",
        "full_name": "The 11th International Conference on Cloud Computing and Big Data Analytics",
        "submission_deadline": "2027-02-15",
        "conference_start": "2027-05-21",
        "conference_end": "2027-05-23",
        "location": "Xihua University, Chengdu, China",
        "topics": ["Cloud Computing", "Big Data Analytics", "Artificial Intelligence"]
    },
    "AIIoT 2027": {
        "conference_name": "AIIoT 2027",
        "full_name": "The International Conference on Artificial Intelligence and Internet of Things",
        "submission_deadline": "2027-03-15",
        "conference_start": "2027-06-18",
        "conference_end": "2027-06-20",
        "location": "Chengdu, China",
        "topics": ["Artificial Intelligence", "Internet of Things", "Edge Computing"]
    }
}


# ================= 2. Python 工具实现 =================
def search_conference(conference_name: str):
    """查询会议详情"""
    # 简单的模糊匹配，容错大小写
    for key, data in conference_data.items():
        if conference_name.lower() in key.lower() or key.lower() in conference_name.lower():
            return data
    return {"error": "Conference not found"}


def days_until(target_date: str):
    """计算距离目标日期的天数"""
    target = date.fromisoformat(target_date)
    today = date.today()
    return {
        "target_date": target_date,
        "today": today.isoformat(),
        "days_remaining": (target - today).days
    }


def get_current_time(timezone: str):
    """查询指定 IANA 时区的当前时间"""
    now = datetime.now(ZoneInfo(timezone))
    return {
        "timezone": timezone,
        "datetime": now.isoformat(),
        "formatted_time": now.strftime("%Y-%m-%d %H:%M:%S")
    }


def convert_timezone(date_str: str, time_str: str, from_timezone: str, to_timezone: str):
    """时区转换"""
    # 兼容模型可能传 "YYYY-MM-DD" 或 "YYYY-MM-DDTHH:MM"
    if "T" in date_str or " " in date_str:
        dt = datetime.fromisoformat(date_str)
    else:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

    src = dt.replace(tzinfo=ZoneInfo(from_timezone))
    dst = src.astimezone(ZoneInfo(to_timezone))
    return {
        "from_timezone": from_timezone,
        "to_timezone": to_timezone,
        "source_datetime": src.isoformat(),
        "target_datetime": dst.isoformat(),
        "formatted_target": dst.strftime("%Y-%m-%d %H:%M:%S")
    }


# ================= 3. 工具 Schema 定义 =================
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_conference",
            "description": "根据会议名称查询会议数据库，返回会议全称、举办时间、举办地点、投稿截止日期和主题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "conference_name": {"type": "string", "description": "会议名称，例如 ICCBDA 2027 或 AIIoT 2027"}
                },
                "required": ["conference_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "days_until",
            "description": "计算距离指定日期（YYYY-MM-DD）还有多少天",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_date": {"type": "string", "description": "目标日期，格式 YYYY-MM-DD"}
                },
                "required": ["target_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "查询指定 IANA 时区的当前时间",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "IANA 时区，如 Asia/Singapore"}
                },
                "required": ["timezone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_timezone",
            "description": "将某个日期时间从源 IANA 时区转换到目标 IANA 时区",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {"type": "string", "description": "日期 YYYY-MM-DD"},
                    "time_str": {"type": "string", "description": "时间 HH:MM"},
                    "from_timezone": {"type": "string", "description": "源 IANA 时区，如 Asia/Tokyo"},
                    "to_timezone": {"type": "string", "description": "目标 IANA 时区，如 Asia/Shanghai"},
                },
                "required": ["date_str", "time_str", "from_timezone", "to_timezone"],
            },
        },
    },
]

# 白名单映射
REGISTRY = {
    "search_conference": (search_conference, ["conference_name"]),
    "days_until": (days_until, ["target_date"]),
    "get_current_time": (get_current_time, ["timezone"]),
    "convert_timezone": (convert_timezone, ["date_str", "time_str", "from_timezone", "to_timezone"]),
}


def validate_and_execute(name: str, args: dict):
    if name not in REGISTRY:
        return {"error": f"未注册工具: {name}"}
    func, required = REGISTRY[name]
    missing = [k for k in required if k not in args]
    if missing:
        return {"error": f"缺少参数: {missing}"}
    try:
        # 只传需要的参数
        return func(**{k: args[k] for k in required})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ================= 4. Agent 执行逻辑 =================
AGENT_SYSTEM = """你是一名学术会议智能查询与时间管理助手。
你可以调用工具查询会议数据库、计算日期差、查询当前时间、转换时区。

规则：
1. 只能依据工具返回结果回答，不得编造会议信息或时间。
2. 如果用户询问会议地点、截稿日期、会议开始时间等，调用 search_conference。
3. 计算天数必须调用 days_until，不要自己计算。
4. 城市名需自动转化为 IANA 时区（如新加坡=Asia/Singapore，纽约=America/New_York，东京=Asia/Tokyo，北京=Asia/Shanghai）。
5. 如果用户问“明天”，请根据当前日期推算具体日期。
6. 当前日期：{today}。
"""


def run_agent(question: str):
    messages = [
        {"role": "system", "content": AGENT_SYSTEM.format(today=date.today().isoformat())},
        {"role": "user", "content": question},
    ]
    logs = []

    for round_no in range(1, 6):
        resp = chat(messages, tools=TOOLS_SCHEMA)
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return msg.content, logs

        # 记录模型发起的工具调用
        assistant_msg = {"role": "assistant", "content": msg.content or ""}
        assistant_msg["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
        messages.append(assistant_msg)

        # 执行工具
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
                result = {"error": "参数解析失败"}
            else:
                t0 = time.time()
                result = validate_and_execute(name, args)
                elapsed = time.time() - t0

            logs.append({
                "round": round_no,
                "tool_name": name,
                "arguments": args,
                "result": result,
                "status": "error" if "error" in result else "ok"
            })

            # 回传给模型
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "工具调用轮次超限，未能完成查询。", logs


# ================= 5. 测试问题 =================
QUESTIONS = {
    "Q1": "ICCBDA 2027 的投稿截止日期是什么时候？距离今天还有多少天？",
    "Q2": "AIIoT 2027 在哪里举办？距离会议开始还有多少天？",
    "Q3": "现在新加坡和纽约分别是几点？",
    "Q4": "东京明天上午9点对应北京时间几点？",
    "Q5": "What is the submission deadline of ICCBDA 2027? How many days are left?",
    "Q6": "帮我查询一个不存在的会议 XYZ 2027 的投稿截止日期。",
}


def main():
    os.makedirs("outputs", exist_ok=True)
    all_logs = {}

    for key, question in QUESTIONS.items():
        print(f"\n===== {key}: {question} =====")
        try:
            answer, logs = run_agent(question)
            all_logs[key] = {"question": question, "answer": answer, "tool_logs": logs}
            print("最终回答：", answer)
            print("工具调用日志：")
            print(json.dumps(logs, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"{key} 运行失败: {e}")

    with open("outputs/exp3_logs.json", "w", encoding="utf-8") as f:
        json.dump(all_logs, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()