import json
from datetime import datetime


class ToolCallLogger:
    def __init__(self):
        self.records = []

    def log(self, step: int, tool_name: str, args: dict, result, status: str, elapsed_ms: float):
        self.records.append({
            "step": step,
            "tool": tool_name,
            "args": args,
            "result": result,
            "status": status,
            "elapsed_ms": round(elapsed_ms, 2),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })

    def dump(self):
        print("\n---- 工具调用记录 ----")
        print(json.dumps(self.records, ensure_ascii=False, indent=2, default=str))

    def clear(self):
        self.records = []