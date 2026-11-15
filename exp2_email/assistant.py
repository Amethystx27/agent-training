import json
from llm_client import chat
from common.json_utils import parse_json_safely
from .schema import EmailAnalysis, ReplyDraft
from .fact_card import FACT_CARD_TEXT


def _analyze_raw(subject: str, sender: str, body: str) -> str:
    user = f"Subject: {subject}\nFrom: {sender}\n\nBody:\n{body}"
    return chat(ANALYSIS_PROMPT, user, temperature=0.0, use_json_mode=True)


def analyze_email(subject: str, sender: str, body: str) -> EmailAnalysis | None:
    raw = _analyze_raw(subject, sender, body)
    ok, data = parse_json_safely(raw)
    if not ok:
        print(f"[分析 JSON 解析失败] {data}")
        return None
    try:
        return EmailAnalysis(**data)
    except Exception as e:
        print(f"[分析 Schema 校验失败] {e}")
        return None


def draft_reply(subject: str, sender: str, body: str,
                analysis: EmailAnalysis) -> ReplyDraft | None:
    user = (
        f"=== 原始邮件 ===\nSubject: {subject}\nFrom: {sender}\n\n{body}\n\n"
        f"=== 邮件分析结果 ===\n{analysis.model_dump_json(indent=2)}\n\n"
        f"=== 会议事实卡 ===\n{FACT_CARD_TEXT}\n"
    )
    raw = chat(REPLY_PROMPT, user, temperature=0.0, use_json_mode=True)
    ok, data = parse_json_safely(raw)
    if not ok:
        print(f"[回复 JSON 解析失败] {data}")
        return None
    try:
        return ReplyDraft(**data)
    except Exception as e:
        print(f"[回复 Schema 校验失败] {e}")
        return None