import json
import re
import time
from openai import OpenAI
from prompts import PROMPT_V1, PROMPT_V2
from validators import validate, check_aiiot_completeness
from notices import NOTICE_A, NOTICE_B, NOTICE_C, NOTICE_AIIOT

BASE_URL = "http://43.142.146.132:8000/v1"
API_KEY = "sk-WXfVsTPZBHxS04ti328942F45f78461c9bA7F1295bE73a34"
MODEL = "deepseek-chat"   # 如服务端模型名不同请调整

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)


def strip_fences(text: str) -> str:
    """容错：去掉模型可能加的 Markdown 围栏与前后解释。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # 截取第一个 { 到最后一个 }
    l, r = text.find("{"), text.rfind("}")
    if l != -1 and r != -1 and r > l:
        return text[l:r + 1]
    return text


def call_model(prompt: str, temperature: float = 0.0) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.choices[0].message.content


def extract(notice: str, prompt_tpl: str, use_json_mode: bool = False):
    prompt = prompt_tpl.format(notice=notice)
    kwargs = {}
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        **kwargs,
    )
    raw = resp.choices[0].message.content
    cleaned = strip_fences(raw)
    try:
        obj = json.loads(cleaned)
        ok = True
    except json.JSONDecodeError as e:
        obj, ok = None, False
        print(f"[JSON 解析失败] {e}\n原文: {raw[:300]}")
    return raw, obj, ok


def run_case(name: str, notice: str):
    print(f"\n{'=' * 70}\n{name}\n{'=' * 70}")
    raw, obj, ok = extract(notice, PROMPT_V2, use_json_mode=False)
    print("---- 模型原始输出 ----")
    print(raw)
    if obj is None:
        print("=> JSON 非法")
        return
    passed, errors = validate(obj)
    print("\n---- 校验结果 ----")
    print("PASS" if passed else "FAIL")
    for e in errors:
        print(" -", e)
    if "AIIoT" in name:
        extra = check_aiiot_completeness(obj)
        print("\n---- AIIoT 专项校验 ----")
        print("PASS" if not extra else "FAIL")
        for e in extra:
            print(" -", e)


def compare_prompts(notice: str, label: str):
    """V1 vs V2 定量对比。"""
    rows = []
    for pname, tpl in [("V1", PROMPT_V1), ("V2", PROMPT_V2)]:
        raw, obj, ok = extract(notice, tpl)
        if not ok or obj is None:
            rows.append((pname, "N/A", "0%", "0%", "0%"))
            continue
        passed, _ = validate(obj)
        field_count = sum(1 for v in obj.values() if v not in (None, [], {}))
        total = len(obj) if obj else 1
        complete_rate = f"{field_count}/{total} ({field_count / total:.0%})"
        raw_str = raw or ""
        # 简单统计字段级准确率（与参考标准比较在 report 中人工核对）
        rows.append((pname, "100%" if ok else "0%",
                     complete_rate, "100%" if passed else "0%", raw_str[:40].replace("\n", " ")))
    print(f"\n==== {label} Prompt 对比 ====")
    print(f"{'Prompt':<8}{'JSON合法率':<12}{'字段完整率':<18}{'校验通过率':<12}")
    for r in rows:
        print(f"{r[0]:<8}{r[1]:<12}{r[2]:<18}{r[3]:<12}")


if __name__ == "__main__":
    for name, notice in [
        ("通知A ICCBDA 2027", NOTICE_A),
        ("通知B Edge Intelligence Forum 2027", NOTICE_B),
        ("通知C Smart Networks 2027", NOTICE_C),
    ]:
        run_case(name, notice)

    run_case("AIIoT 2027（进阶）", NOTICE_AIIOT)

    for label, notice in [("通知A", NOTICE_A), ("通知B", NOTICE_B),
                          ("通知C", NOTICE_C), ("AIIoT", NOTICE_AIIOT)]:
        compare_prompts(notice, label)