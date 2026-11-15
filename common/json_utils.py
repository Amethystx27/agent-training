import json
from typing import Tuple, Any


def parse_json_safely(raw: str) -> Tuple[bool, Any]:
    """容忍 Markdown 围栏与前后多余文字，尽量解析出 JSON 对象。"""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return True, json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return True, json.loads(text[start:end + 1])
        except Exception as e:
            return False, f"JSON 解析失败: {e}"
    return False, "未找到 JSON 对象"