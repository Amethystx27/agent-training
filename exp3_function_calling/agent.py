import json
from datetime import datetime
from llm_client import chat_with_tools
from .tool_schemas import TOOLS
from .tools import TOOL_REGISTRY

SYSTEM_PROMPT = """你是一个学术会议智能查询与时间管理助手。
- 你可以调用工具来查询会议信息、当前时间、日期差和时区转换。
- 只能使用提供的工具，不要编造会议数据或计算结果。
- 复合问题请依次调用多个工具（如先查询会议截止日期，再计算剩余天数）。
- 用户用中文或英文都可以，回答语言与用户一致。
- 若信息缺失或有歧义（如未说明城市），先向用户澄清，不要猜测。
- 工具返回 error 时，如实告知用户，不得伪造成功结果。
"""


def _run_tool(name: str, args: dict) -> dict:
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": f"未注册的工具: {name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"参数错误: {e}"}
    except Exception as e:
        return {"error": f"工具执行异常: {e}"}


def run_agent(user_query: str, max_rounds: int = 6, verbose: bool = True) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]
    call_log = []

    for _ in range(max_rounds):
        msg = chat_with_tools(messages, TOOLS, tool_choice="auto")
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name,
                              "arguments": tc.function.arguments}}
                for tc in (msg.tool_calls or [])
            ] if msg.tool_calls else None,
        })

        if not msg.tool_calls:
            if verbose:
                print("\n---- 最终回答 ----")
                print(msg.content)
            return {"answer": msg.content, "log": call_log}

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception as e:
                args = {}
                result = {"error": f"参数 JSON 解析失败: {e}"}
            else:
                result = _run_tool(name, args)

            call_log.append({
                "tool": name, "args": args,
                "result": result,
                "time": datetime.now().isoformat(timespec="seconds"),
            })
            if verbose:
                print(f"\n[TOOL] {name}({args}) -> {json.dumps(result, ensure_ascii=False)}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    return {"answer": "达到最大工具调用轮数，未得到最终回答。", "log": call_log}