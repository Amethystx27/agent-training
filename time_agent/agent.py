import json
import time
from openai import OpenAI

from tools import TOOL_REGISTRY
from tool_schemas import TOOLS
from logger import ToolCallLogger

BASE_URL = "http://43.142.146.132:8000/v1"
API_KEY = "sk-WXfVsTPZBHxS04ti328942F45f78461c9bA7F1295bE73a34"
MODEL = "deepseek-chat"

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

SYSTEM_PROMPT = """你是一名学术会议智能查询助手。
- 用户可能用中文或英文提问。请用与用户相同的语言回答。
- 你可以调用工具查询会议信息、当前时间、日期差和时区转换。
- 涉及"还剩多少天""距离会议还有多久"等计算，必须先调用工具获取真实数据，不得自行心算。
- 若用户未明确会议名称、城市或日期，先追问澄清，不要猜测。
- 工具返回 error 时，如实告知用户，不得编造结果。
- 回答时给出关键数据来源（如会议截止日期、剩余天数）。
"""


def run_agent(user_question: str, logger: ToolCallLogger, max_steps: int = 8) -> str:
    logger.clear()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_question},
    ]

    for step in range(1, max_steps + 1):
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.0,
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            # 模型给出最终回答
            return msg.content or ""

        for tc in tool_calls:
            name = tc.function.name
            raw_args = tc.function.arguments or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}
                logger.log(step, name, raw_args, "JSON 参数解析失败", "error", 0)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps({"error": "Invalid JSON arguments"}, ensure_ascii=False),
                })
                continue

            fn = TOOL_REGISTRY.get(name)
            if fn is None:
                result = {"error": f"Unknown tool: {name}"}
                status = "error"
                elapsed = 0
            else:
                t0 = time.time()
                try:
                    result = fn(**args)
                    status = "error" if isinstance(result, dict) and "error" in result else "success"
                except Exception as e:
                    result = {"error": f"Tool execution failed: {e}"}
                    status = "error"
                elapsed = (time.time() - t0) * 1000

            logger.log(step, name, args, result, status, elapsed)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    return "[超过最大工具调用步数，未得到最终回答]"