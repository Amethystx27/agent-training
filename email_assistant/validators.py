import json
import re

INTENTS = {
    "registration_inquiry", "submission_deadline", "acceptance_inquiry",
    "payment_inquiry", "accommodation_inquiry", "certificate_request",
    "paper_update_request", "technical_issue", "other",
}

FORCE_REVIEW_INTENTS = {"acceptance_inquiry", "paper_update_request"}
FORCE_REVIEW_KEYWORDS = ["refund", "invoice", "payment", "accepted", "acceptance"]


def strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    l, r = text.find("{"), text.rfind("}")
    if l != -1 and r != -1 and r > l:
        return text[l:r + 1]
    return text


def parse_json(raw: str):
    try:
        return json.loads(strip_fences(raw)), True
    except json.JSONDecodeError:
        return None, False


def validate_analysis(obj: dict) -> list[str]:
    errs = []
    required = ["sender", "subject", "conference_name", "primary_intent",
                "secondary_intents", "user_role", "questions",
                "extracted_entities", "requires_human_review", "review_reason"]
    for f in required:
        if f not in obj:
            errs.append(f"缺少字段: {f}")
    if obj.get("primary_intent") not in INTENTS:
        errs.append(f"primary_intent 非法: {obj.get('primary_intent')!r}")
    sec = obj.get("secondary_intents")
    if sec is not None and not isinstance(sec, list):
        errs.append("secondary_intents 必须是数组或 null")
    elif isinstance(sec, list):
        for s in sec:
            if s not in INTENTS:
                errs.append(f"secondary_intents 含非法类别: {s!r}")
    if not isinstance(obj.get("questions"), list):
        errs.append("questions 必须是数组")
    if not isinstance(obj.get("requires_human_review"), bool):
        errs.append("requires_human_review 必须是布尔值")
    return errs


def check_review_consistency(analysis: dict, email_text: str) -> list[str]:
    """业务规则：退款/付款/录用/变更必须人工审核。"""
    warns = []
    text_lower = email_text.lower()
    intents = {analysis.get("primary_intent")} | set(analysis.get("secondary_intents") or [])
    if intents & FORCE_REVIEW_INTENTS and not analysis.get("requires_human_review"):
        warns.append("业务规则违规：含 acceptance/paper_update 意图却未标记人工审核")
    if any(k in text_lower for k in FORCE_REVIEW_KEYWORDS) and not analysis.get("requires_human_review"):
        warns.append("业务规则违规：邮件含退款/发票/付款/录用关键词却未标记人工审核")
    return warns


def validate_reply(obj: dict) -> list[str]:
    errs = []
    for f in ["subject", "body", "requires_human_review", "review_reason"]:
        if f not in obj:
            errs.append(f"回复缺少字段: {f}")
    if not isinstance(obj.get("requires_human_review"), bool):
        errs.append("回复 requires_human_review 必须是布尔值")
    body = (obj.get("body") or "").lower()
    # 禁止模型擅自承诺退款/确认付款/给出录用结论
    forbidden = ["you will receive a full refund", "refund has been approved",
                 "your payment has been received", "your paper has been accepted",
                 "your paper is accepted", "we confirm the acceptance"]
    for bad in forbidden:
        if bad in body:
            errs.append(f"回复含禁止承诺语句: {bad!r}")
    if obj.get("requires_human_review") and "[human review required]" not in body:
        errs.append("人工审核邮件正文缺少 [HUMAN REVIEW REQUIRED] 标记")
    return errs


def validate_style_reply(obj: dict) -> list[str]:
    errs = []
    for style in ["formal", "concise", "friendly"]:
        if style not in obj or not isinstance(obj[style], dict):
            errs.append(f"缺少风格: {style}")
            continue
        if "subject" not in obj[style] or "body" not in obj[style]:
            errs.append(f"{style} 缺少 subject/body")
    return errs