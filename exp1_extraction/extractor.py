import json
from llm_client import chat
from .validator import validate


def extract(prompt: str, notice_text: str, label: str = "", verbose: bool = True):
    print(f"\n{'='*70}\n>>> 抽取: {label}\n{'='*70}")
    raw = chat(prompt, notice_text, temperature=0.0, use_json_mode=True)
    if verbose:
        print("---- 模型原始输出 ----")
        print(raw)
    ok, info, issues = validate(raw)
    print("\n---- 校验结果 ----")
    print("✅ 通过" if ok else "❌ 未通过：")
    if not ok:
        for i in issues:
            print("  -", i)
    if info:
        print("\n---- 结构化结果 ----")
        print(json.dumps(info.model_dump(), ensure_ascii=False, indent=2))
    return {"label": label, "raw": raw, "ok": ok, "info": info, "issues": issues}