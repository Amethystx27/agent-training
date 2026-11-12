import json
import time
from openai import OpenAI

from facts import ICCBDA_FACTS, AIIOT_FACTS, facts_to_text
from emails import EMAILS
from prompts import (ANALYZE_PROMPT, REPLY_PROMPT, SINGLE_LABEL_PROMPT,
                     MULTI_LABEL_PROMPT, STYLE_REPLY_PROMPT)
from validators import (parse_json, validate_analysis, check_review_consistency,
                        validate_reply, validate_style_reply)

BASE_URL = "http://43.142.146.132:8000/v1"
API_KEY = "sk-WXfVsTPZBHxS04ti328942F45f78461c9bA7F1295bE73a34"
MODEL = "gpt-4o"   # ← 换成 list_models.py 查到的真实模型名

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)


def call_model(prompt: str, temperature: float = 0.0) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.choices[0].message.content


def safe_json(raw: str):
    obj, ok = parse_json(raw)
    if not ok:
        # 修复重试：让模型只输出 JSON
        fix = call_model(f"将下面内容整理为合法 JSON，只输出 JSON：\n{raw}")
        obj, ok = parse_json(fix)
    return obj, ok


# ---------- 主流程：分析 + 回复 ----------
def process_email(tag: str, email: dict, facts: dict):
    print(f"\n{'=' * 72}\n邮件 {tag}: {email['subject']}\n{'=' * 72}")

    raw1 = call_model(ANALYZE_PROMPT.format(
        sender=email["from"], subject=email["subject"], body=email["body"]))
    analysis, ok = safe_json(raw1)
    print("---- 分析原始输出 ----")
    print(raw1)
    if ok:
        errs = validate_analysis(analysis) + check_review_consistency(analysis, email["body"])
        print("---- 分析校验 ----", "PASS" if not errs else "FAIL")
        for e in errs:
            print(" -", e)

    if not ok:
        print("[跳过回复生成：分析 JSON 非法]")
        return

    raw2 = call_model(REPLY_PROMPT.format(
        facts=facts_to_text(facts),
        subject=email["subject"],
        body=email["body"],
        analysis=json.dumps(analysis, ensure_ascii=False, indent=2)))
    reply, ok2 = safe_json(raw2)
    print("\n---- 回复原始输出 ----")
    print(raw2)
    if ok2:
        errs = validate_reply(reply)
        print("---- 回复校验 ----", "PASS" if not errs else "FAIL")
        for e in errs:
            print(" -", e)


# ---------- 进阶：单标签 vs 多标签 ----------
def classify_compare(email_body: str):
    print(f"\n{'=' * 72}\n单标签 vs 多标签分类对比\n{'=' * 72}")
    raw_s = call_model(SINGLE_LABEL_PROMPT.format(body=email_body))
    single, _ = safe_json(raw_s)
    raw_m = call_model(MULTI_LABEL_PROMPT.format(body=email_body))
    multi, _ = safe_json(raw_m)
    print("单标签:", raw_s)
    print("多标签:", raw_m)

    expected = {"registration_inquiry", "accommodation_inquiry", "payment_inquiry"}
    s_labels = {single.get("label")} if single else set()
    m_labels = set(multi.get("labels", [])) if multi else set()
    print(f"预期集合: {sorted(expected)}")
    print(f"单标签召回: {len(s_labels & expected)}/{len(expected)} -> {sorted(s_labels)}")
    print(f"多标签召回: {len(m_labels & expected)}/{len(expected)} -> {sorted(m_labels)}")
    return single, multi, expected


# ---------- 进阶：三风格回复 ----------
def style_reply(email_body: str, facts: dict, analysis: dict):
    print(f"\n{'=' * 72}\n三风格回复生成\n{'=' * 72}")
    raw = call_model(STYLE_REPLY_PROMPT.format(
        facts=facts_to_text(facts),
        body=email_body,
        analysis=json.dumps(analysis, ensure_ascii=False, indent=2)))
    obj, ok = safe_json(raw)
    print(raw)
    if ok:
        errs = validate_style_reply(obj)
        print("---- 三风格校验 ----", "PASS" if not errs else "FAIL")
        for e in errs:
            print(" -", e)
    return obj


if __name__ == "__main__":
    # 邮件 A–F，用 ICCBDA 事实卡
    for tag in ["A", "B", "C", "D", "E", "F"]:
        process_email(tag, EMAILS[tag], ICCBDA_FACTS)

    # 进阶挑战：AIIoT 复杂邮件
    adv = EMAILS["ADV"]
    process_email("ADV", adv, AIIOT_FACTS)

    # 单标签 vs 多标签
    classify_compare(adv["body"])

    # 三风格回复
    raw = call_model(ANALYZE_PROMPT.format(
        sender=adv["from"], subject=adv["subject"], body=adv["body"]))
    analysis, ok = safe_json(raw)
    if ok:
        style_reply(adv["body"], AIIOT_FACTS, analysis)