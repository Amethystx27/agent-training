import json
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from common import chat, extract_json


INTENTS = {
    "registration_inquiry",
    "submission_deadline",
    "acceptance_inquiry",
    "payment_inquiry",
    "accommodation_inquiry",
    "certificate_request",
    "paper_update_request",
    "technical_issue",
    "other",
}


FACTS = """会议名称：ICCBDA 2027
会议日期：May 21–23, 2027
地点：Xihua University, Chengdu, China
全文投稿截止日期：February 15, 2027
学生作者注册费：USD 350
普通作者注册费：USD 450
听众注册费：USD 180
住宿信息：尚未公布，请关注会议官方通知
录用结果：只能通过投稿系统查询；邮件中不提供个人录用结论
退款政策：未提供正式政策，必须转人工确认
联系邮箱：iccbda2027@example.org
"""


ANALYZE_SYSTEM = """你是一名国际学术会议邮件分类助手。
请分析邮件并返回 JSON，字段包括：
sender, subject, conference_name, primary_intent, secondary_intents,
user_role, questions, extracted_entities, requires_human_review,
review_reason。

分类只能使用：
registration_inquiry, submission_deadline, acceptance_inquiry,
payment_inquiry, accommodation_inquiry, certificate_request,
paper_update_request, technical_issue, other。

规则：
- 不确定的信息使用 null。
- 不得将用户陈述当作已经核实的事实。
- 退款、付款争议、录用结果、作者信息变更必须人工审核。
- 一封邮件有多个问题时全部提取。
- 只输出合法 JSON。
"""


REPLY_SYSTEM = """你是一名专业、礼貌的国际学术会议秘书。
请根据原始邮件、邮件分析结果和会议事实卡生成英文回复草稿。

规则：
1. 只使用会议事实卡明确提供的信息。
2. 不得承诺退款、确认付款或判断论文录用结果。
3. 对未提供的信息，说明目前无法确认，并建议联系秘书处。
4. 需要人工审核的邮件，生成谨慎的确认收悉草稿，并标注 [HUMAN REVIEW REQUIRED]。
5. 输出 subject、body、requires_human_review、review_reason。
6. 不发送邮件，只生成草稿。
7. 只输出合法 JSON。
"""


class EmailAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sender: Optional[str] = None
    subject: Optional[str] = None
    conference_name: Optional[str] = None
    primary_intent: str
    secondary_intents: List[str] = Field(default_factory=list)
    user_role: Optional[str] = None
    questions: List[str] = Field(default_factory=list)
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    requires_human_review: bool
    review_reason: Optional[str] = None

    @field_validator("primary_intent")
    @classmethod
    def validate_primary_intent(cls, v):
        if v not in INTENTS:
            raise ValueError(f"非法主意图: {v}")
        return v

    @field_validator("secondary_intents")
    @classmethod
    def validate_secondary_intents(cls, v):
        for x in v:
            if x not in INTENTS:
                raise ValueError(f"非法次级意图: {x}")
        return v


class ReplyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str
    body: str
    requires_human_review: bool
    review_reason: Optional[str] = None


def analyze_email(email: Dict[str, str]) -> EmailAnalysis:
    user_content = (
        f"From: {email['from']}\n"
        f"Subject: {email['subject']}\n"
        f"Body:\n{email['body']}"
    )
    messages = [
        {"role": "system", "content": ANALYZE_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    resp = chat(messages, response_format={"type": "json_object"})
    raw_text = resp.choices[0].message.content
    raw_json = extract_json(raw_text)
    return EmailAnalysis.model_validate(raw_json)


def apply_review_policy(analysis: EmailAnalysis, body: str) -> EmailAnalysis:
    intents = {analysis.primary_intent} | set(analysis.secondary_intents)
    need_review = bool(
        intents & {"acceptance_inquiry", "payment_inquiry", "paper_update_request"}
    )
    if "refund" in body.lower():
        need_review = True

    if need_review:
        analysis.requires_human_review = True
        extra = "自动规则：录用结果、付款退款、退款申请或论文变更类事项需人工核验。"
        if not analysis.review_reason:
            analysis.review_reason = extra
        elif extra not in analysis.review_reason:
            analysis.review_reason = f"{analysis.review_reason}；{extra}"
    return analysis


def generate_reply(email: Dict[str, str], analysis: Dict[str, Any]) -> ReplyDraft:
    user_content = (
        f"【会议事实卡】\n{FACTS}\n\n"
        f"【原始邮件】\nFrom: {email['from']}\n"
        f"Subject: {email['subject']}\nBody:\n{email['body']}\n\n"
        f"【邮件分析结果】\n{json.dumps(analysis, ensure_ascii=False, indent=2)}"
    )
    messages = [
        {"role": "system", "content": REPLY_SYSTEM},
        {"role": "user", "content": user_content},
    ]
    resp = chat(messages, response_format={"type": "json_object"})
    raw_text = resp.choices[0].message.content
    raw_json = extract_json(raw_text)
    draft = ReplyDraft.model_validate(raw_json)

    if analysis.get("requires_human_review"):
        draft.requires_human_review = True
        if not draft.review_reason:
            draft.review_reason = analysis.get("review_reason")
        marker = "[HUMAN REVIEW REQUIRED]"
        if marker not in draft.body:
            draft.body = f"{marker}\n\n{draft.body}"

    return draft


EMAILS = {
    "A": {
        "from": "john.smith@example.net",
        "subject": "Inquiry About Registration Fee and Submission Deadline",
        "body": """Dear Conference Organizing Committee,

I am interested in attending ICCBDA 2027. Could you please confirm whether the registration fee for student authors is USD 350?

I would also like to know the full paper submission deadline, as I am preparing my manuscript.

Thank you for your assistance.

Best regards,
John Smith""",
    },
    "B": {
        "from": "maria.chen@example.net",
        "subject": "Request for Paper Acceptance Status",
        "body": """Dear Organizing Committee,

I submitted a paper entitled "Privacy-Preserving Edge Intelligence for IoT Networks" to ICCBDA 2027 two weeks ago.

Could you let me know whether my paper has been accepted? I need the decision soon to arrange my travel.

Best regards,
Maria Chen""",
    },
    "C": {
        "from": "david.lee@example.net",
        "subject": "Payment Confirmation and Invoice Request",
        "body": """Dear Conference Secretariat,

I completed the registration payment yesterday, but I have not received a confirmation email.

Could you please check whether my payment has been received? I would also like to request an official invoice for my university reimbursement.

My registration email is david.lee@example.net.

Thank you,
David Lee""",
    },
    "D": {
        "from": "anna.wilson@example.net",
        "subject": "Accommodation and Transportation Information",
        "body": """Dear Organizing Committee,

I plan to attend ICCBDA 2027 in Chengdu. Could you recommend hotels near the conference venue?

I would also appreciate information about transportation from Chengdu Tianfu International Airport to the university.

Best regards,
Anna Wilson""",
    },
    "E": {
        "from": "peter.brown@example.net",
        "subject": "Request for Registration Fee Refund",
        "body": """Dear Secretariat,

Unfortunately, I can no longer attend ICCBDA 2027 due to an unexpected change in my schedule.

I have already paid the registration fee. Could you please let me know whether I can receive a full refund and how long the process will take?

I would appreciate your help.

Sincerely,
Peter Brown""",
    },
    "F": {
        "from": "liu.yang@example.net",
        "subject": "Unable to Upload My Manuscript",
        "body": """Dear Technical Support Team,

I am trying to upload my paper to the submission system, but the page keeps showing an error after I click the Submit button.

I have tried using two different browsers, but the problem remains.

Could you please advise me on how to proceed?

Best regards,
Yang Liu""",
    },
}


def main():
    os.makedirs("outputs", exist_ok=True)
    all_results = {}

    for key, email in EMAILS.items():
        print(f"\n===== 邮件 {key} =====")
        try:
            analysis = analyze_email(email)
            analysis = apply_review_policy(analysis, email["body"])
            draft = generate_reply(email, analysis.model_dump())

            result = {
                "email_key": key,
                "analysis": analysis.model_dump(),
                "reply_draft": draft.model_dump(),
            }
            all_results[key] = result
            print(json.dumps(result, ensure_ascii=False, indent=2))

        except (ValidationError, ValueError, Exception) as e:
            print(f"邮件 {key} 处理失败: {type(e).__name__}: {e}")

    with open("outputs/exp2_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()