import json
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")


def chat(messages, tools=None, response_format=None, temperature=0):
    kwargs = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if tools is not None:
        kwargs["tools"] = tools
        # DeepSeek 思考模式下只接受 auto，不要用 required
        kwargs["tool_choice"] = "auto"
        # 可选：关闭思考模式，使工具调用更稳定、更快
        # kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    return client.chat.completions.create(**kwargs)


def extract_json(text):
    """DeepSeek JSON 模式下仍建议做兜底清洗。"""
    if text is None:
        raise ValueError("模型返回为空")
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        i = s.find("{")
        j = s.rfind("}")
        if i < 0 or j <= i:
            raise
        return json.loads(s[i:j + 1])