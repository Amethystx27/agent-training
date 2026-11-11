"""
实验2：会议邮件智能回复助手 (Meeting Email Smart-Reply Assistant)
================================================================
基础实验（不含进阶挑战）：
  1. 读取英文会议咨询邮件（主题/发件人/正文）
  2. 调用大模型识别主意图 + 次级意图，提取问题、身份、论文标题等
  3. 依据「会议事实卡」判断哪些问题可回答、哪些必须人工审核
  4. 生成英文回复草稿（含 [HUMAN REVIEW REQUIRED] 标记与理由）
  5. 对邮件 A–F 逐一测试，保存分析结果 + 回复草稿

运行：
  # 真实调用 API（需要 .env 中配置 API_KEY / API_BASE / MODEL）
  python main.py --all
  python main.py --email emails/email_A.txt

  # 离线演示（不依赖网络，使用内置预设答案与事实卡规则）
  python main.py --all --mock
"""
import os
import json
import argparse
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

# ----------------------------------------------------------------------------
# 1. 加载配置
# ----------------------------------------------------------------------------
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
API_KEY = os.getenv("API_KEY")
API_BASE = os.getenv("API_BASE")
MODEL = os.getenv("MODEL", "deepseek-flash")
client = OpenAI(api_key=API_KEY, base_url=API_BASE) if API_KEY else None

# ----------------------------------------------------------------------------
# 2. 会议事实卡（唯一可信依据，模型只能依据此卡回复，不得编造）
# ----------------------------------------------------------------------------
FACT_CARD = {
    "conference_name": "ICCBDA 2027",
    "conference_dates": "May 21-23, 2027",
    "location": "Xihua University, Chengdu, China",
    "full_paper_deadline": "February 15, 2027",
    "registration_fees": {
        "student_author": "USD 350",
        "regular_author": "USD 450",
        "audience": "USD 180",
    },
    "accommodation": "尚未公布，请关注会议官方通知",
    "acceptance_result": "只能通过投稿系统查询；邮件中不提供个人录用结论",
    "refund_policy": "未提供正式政策，必须转人工确认",
    "contact_email": "iccbda2027@example.org",
}

# 邮件意图类别（基础实验的 9 类）
INTENT_LABELS = [
    "registration_inquiry",   # 注册流程 / 参会身份 / 注册类别
    "submission_deadline",    # 投稿截止日期
    "acceptance_inquiry",     # 录用结果 / 审稿进度
    "payment_inquiry",        # 付款 / 发票 / 退款 / 付款状态
    "accommodation_inquiry",  # 酒店 / 住宿 / 交通
    "certificate_request",    # 参会 / 录用证明
    "paper_update_request",   # 论文修改 / 作者信息变更 / 撤稿
    "technical_issue",        # 投稿 / 注册系统技术问题
    "other",                  # 其他
]

# 必须转人工审核的意图（依据指导书规则）
HUMAN_REVIEW_INTENTS = {"acceptance_inquiry", "payment_inquiry", "paper_update_request"}

# ----------------------------------------------------------------------------
# 3. Pydantic 校验模型
# ----------------------------------------------------------------------------
class EmailAnalysis(BaseModel):
    sender: Optional[str] = None
    subject: Optional[str] = None
    conference_name: Optional[str] = None
    primary_intent: str
    secondary_intents: list[str] = Field(default_factory=list)
    user_role: Optional[str] = None
    questions: list[str] = Field(default_factory=list)
    extracted_entities: dict = Field(default_factory=dict)
    requires_human_review: bool = False
    review_reason: Optional[str] = None


class ReplyDraft(BaseModel):
    subject: str
    body: str
    requires_human_review: bool
    review_reason: Optional[str] = None


# ----------------------------------------------------------------------------
# 4. Prompt 设计
# ----------------------------------------------------------------------------
SYSTEM_ANALYZE = (
    "你是一名国际学术会议邮件分类助手。请分析邮件并返回 JSON。"
    "字段包括：sender, subject, conference_name, primary_intent, "
    "secondary_intents, user_role, questions, extracted_entities, "
    "requires_human_review, review_reason。"
    f"primary_intent 只能使用以下类别之一：{', '.join(INTENT_LABELS)}。"
    "secondary_intents 是其余相关意图的列表（可空）。"
    "规则：\n"
    "- 不确定的信息使用 null。\n"
    "- 不得将用户陈述当作已经核实的事实。\n"
    "- 退款、付款争议、录用结果、作者信息变更必须人工审核"
    "（requires_human_review 设为 true 并在 review_reason 说明）。\n"
    "- 一封邮件有多个问题时，questions 全部提取。\n"
    "- 只输出合法 JSON，不要输出 Markdown 代码围栏或解释。"
)

SYSTEM_REPLY = (
    "你是一名专业、礼貌的国际学术会议秘书。请根据原始邮件、邮件分析结果和"
    "「会议事实卡」生成英文回复草稿。\n"
    "会议事实卡（唯一可信依据）：\n"
    f"{json.dumps(FACT_CARD, ensure_ascii=False, indent=2)}\n"
    "规则：\n"
    "1. 只使用会议事实卡明确提供的信息。\n"
    "2. 不得承诺退款、确认付款或判断论文录用结果。\n"
    "3. 对未提供的信息，说明目前无法确认，并建议联系秘书处。\n"
    "4. 需要人工审核的邮件，生成谨慎的确认收悉草稿，并标注 [HUMAN REVIEW REQUIRED]。\n"
    "5. 输出字段：subject, body, requires_human_review, review_reason。\n"
    "6. 不发送邮件，只生成草稿。\n"
    "7. 只输出合法 JSON。"
)


# ----------------------------------------------------------------------------
# 5. 与模型交互
# ----------------------------------------------------------------------------
def _chat_json(system: str, user: str) -> dict:
    if client is None:
        raise RuntimeError("未配置 API（缺少 API_KEY / API_BASE），请使用 --mock 模式。")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)


def analyze_email(text: str) -> EmailAnalysis:
    data = _chat_json(SYSTEM_ANALYZE, text)
    return EmailAnalysis(**data)


def generate_reply(text: str, analysis: EmailAnalysis) -> ReplyDraft:
    user_msg = (
        f"原始邮件：\n{text}\n\n"
        f"邮件分析结果（JSON）：\n{analysis.model_dump_json(indent=2)}"
    )
    data = _chat_json(SYSTEM_REPLY, user_msg)
    return ReplyDraft(**data)


# ----------------------------------------------------------------------------
# 6. 离线 Mock（不依赖网络，用于演示与自检）
# ----------------------------------------------------------------------------
MOCK_ANALYSES = {
    "email_A": EmailAnalysis(
        sender="john.smith@example.net",
        subject="Inquiry About Registration Fee and Submission Deadline",
        conference_name="ICCBDA 2027",
        primary_intent="registration_inquiry",
        secondary_intents=["submission_deadline"],
        user_role=" prospective attendee / author",
        questions=[
            "Confirm the student author registration fee is USD 350.",
            "What is the full paper submission deadline?",
        ],
        extracted_entities={"fee_inquiry": "student author USD 350"},
        requires_human_review=False,
    ),
    "email_B": EmailAnalysis(
        sender="maria.chen@example.net",
        subject="Request for Paper Acceptance Status",
        conference_name="ICCBDA 2027",
        primary_intent="acceptance_inquiry",
        user_role="author",
        questions=["Has my paper been accepted?"],
        extracted_entities={
            "paper_title": "Privacy-Preserving Edge Intelligence for IoT Networks",
            "submitted": "two weeks ago",
        },
        requires_human_review=True,
        review_reason="录用结果只能通过投稿系统查询，邮件中不提供个人录用结论，需人工/系统核实。",
    ),
    "email_C": EmailAnalysis(
        sender="david.lee@example.net",
        subject="Payment Confirmation and Invoice Request",
        conference_name="ICCBDA 2027",
        primary_intent="payment_inquiry",
        user_role="registered participant",
        questions=[
            "Has my payment been received?",
            "Request an official invoice for university reimbursement.",
        ],
        extracted_entities={"registration_email": "david.lee@example.net"},
        requires_human_review=True,
        review_reason="付款状态与发票需秘书处核实，不得声称已查到付款。",
    ),
    "email_D": EmailAnalysis(
        sender="anna.wilson@example.net",
        subject="Accommodation and Transportation Information",
        conference_name="ICCBDA 2027",
        primary_intent="accommodation_inquiry",
        user_role="prospective attendee",
        questions=[
            "Recommend hotels near the conference venue.",
            "Transportation from Chengdu Tianfu International Airport to the university.",
        ],
        extracted_entities={"city": "Chengdu", "venue": "Xihua University"},
        requires_human_review=False,
    ),
    "email_E": EmailAnalysis(
        sender="peter.brown@example.net",
        subject="Request for Registration Fee Refund",
        conference_name="ICCBDA 2027",
        primary_intent="payment_inquiry",
        user_role="registered participant",
        questions=[
            "Can I receive a full refund?",
            "How long will the refund process take?",
        ],
        requires_human_review=True,
        review_reason="退款政策未提供，必须转人工确认。",
    ),
    "email_F": EmailAnalysis(
        sender="liu.yang@example.net",
        subject="Unable to Upload My Manuscript",
        conference_name="ICCBDA 2027",
        primary_intent="technical_issue",
        user_role="author",
        questions=["Upload fails with an error after clicking Submit; advise how to proceed."],
        extracted_entities={"error": "page shows error after Submit", "browsers_tried": 2},
        requires_human_review=False,
    ),
}


def mock_reply(analysis: EmailAnalysis) -> ReplyDraft:
    """基于事实卡的简单规则回复（离线演示用）。"""
    fee = FACT_CARD["registration_fees"]
    fee_block = "\n".join(f"- {k.replace('_', ' ').title()}: {v}" for k, v in fee.items())

    if analysis.requires_human_review:
        body = (
            f"Dear {analysis.sender or 'Sir/Madam'},\n\n"
            f"Thank you for your email regarding {FACT_CARD['conference_name']}. "
            f"We have received your message and noted your inquiry.\n\n"
            f"Please note that this matter requires verification by our secretariat and "
            f"cannot be confirmed by automated reply. A member of our team will follow up "
            f"with you shortly.\n\n"
            f"[HUMAN REVIEW REQUIRED]\n\n"
            f"Best regards,\nICCBDA 2027 Organizing Committee"
        )
        return ReplyDraft(
            subject=f"Re: {analysis.subject or 'Your inquiry about ICCBDA 2027'}",
            body=body,
            requires_human_review=True,
            review_reason=analysis.review_reason,
        )

    intents = [analysis.primary_intent] + analysis.secondary_intents
    parts = []
    if "submission_deadline" in intents:
        parts.append(f"The full paper submission deadline is {FACT_CARD['full_paper_deadline']}.")
    if "registration_inquiry" in intents:
        parts.append("The registration fees are as follows:\n" + fee_block)
    if "accommodation_inquiry" in intents:
        parts.append(
            f"Accommodation information is {FACT_CARD['accommodation']}. "
            "We will announce hotel and transportation details on the official website."
        )
    if "technical_issue" in intents:
        parts.append(
            "For the submission system issue, please send us a screenshot of the error "
            "message, your paper submission ID, and the browser/version you are using, "
            "so our technical team can assist you."
        )
    if not parts:
        parts.append("Thank you for your email. We will get back to you with the relevant information.")

    body = (
        f"Dear {analysis.sender or 'Sir/Madam'},\n\n"
        + "\n\n".join(parts) + "\n\n"
        + f"If you need further assistance, please contact {FACT_CARD['contact_email']}.\n\n"
        + "Best regards,\nICCBDA 2027 Organizing Committee"
    )
    return ReplyDraft(
        subject=f"Re: {analysis.subject or 'Your inquiry about ICCBDA 2027'}",
        body=body,
        requires_human_review=False,
        review_reason=None,
    )


# ----------------------------------------------------------------------------
# 7. 处理流程
# ----------------------------------------------------------------------------
def process_email(text: str, email_id: str, use_mock: bool):
    if use_mock or client is None:
        analysis = MOCK_ANALYSES.get(email_id) or analyze_email(text)
        reply = mock_reply(analysis)
    else:
        analysis = analyze_email(text)
        reply = generate_reply(text, analysis)
    return analysis, reply


def main():
    parser = argparse.ArgumentParser(description="实验2：会议邮件智能回复助手")
    parser.add_argument("--email", help="处理单个邮件文件")
    parser.add_argument("--all", action="store_true", help="处理 emails/ 下全部邮件")
    parser.add_argument("--mock", action="store_true", help="离线演示模式（不调用 API）")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    results = []

    if args.email:
        path = Path(args.email)
        if not path.is_absolute():
            path = base / path
        text = path.read_text(encoding="utf-8")
        email_id = path.stem
        analysis, reply = process_email(text, email_id, args.mock)
        results.append({"id": email_id, "analysis": analysis.model_dump(), "reply": reply.model_dump()})
    elif args.all:
        for p in sorted((base / "emails").glob("email_*.txt")):
            text = p.read_text(encoding="utf-8")
            analysis, reply = process_email(text, p.stem, args.mock)
            results.append({"id": p.stem, "analysis": analysis.model_dump(), "reply": reply.model_dump()})
    else:
        parser.print_help()
        return

    # 保存结构化结果
    out = base / "results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # 控制台摘要
    for r in results:
        a = r["analysis"]
        rp = r["reply"]
        flag = "🔴 需人工审核" if a["requires_human_review"] else "🟢 自动可答"
        print(f"\n===== {r['id']} =====")
        print(f"发件人 : {a['sender']}")
        print(f"主意图 : {a['primary_intent']}  (次级: {a['secondary_intents']})")
        print(f"问题   : {a['questions']}")
        print(f"审核   : {flag}" + (f" — {a['review_reason']}" if a['review_reason'] else ""))
        print(f"回复主题: {rp['subject']}")
        print("-" * 40)
        print(rp["body"])
    print(f"\n✅ 已保存 {len(results)} 封邮件的分析与回复到 {out}")


if __name__ == "__main__":
    main()
