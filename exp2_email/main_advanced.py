import json
from llm_client import chat
from common.json_utils import parse_json_safely

ADV_EMAIL = {
    "subject": "Quick Qs about AIIoT 2027 registration, hotel and invoice",
    "from": "emily.johnson@example.net",
    "body": """Dear Conference Team,
Hope you are doing well!
I'm planning to attend AIIoT 2027, but I have a few quick questions.
First, I'm a PhD student and will be presenting a paper at the conference. Can I still get the student registration rate? I saw the student fee is USD 280 for early bird registration. Is that correct? Also, if I pay next week, will I still be able to get this price?
Second, do you have any recommended hotels near the conference venue? I would prefer a hotel within walking distance, maybe with a special discount for conference participants. How much would it cost per night? Is breakfast included?
Finally, I need an official invoice for my university's reimbursement. Can you issue an invoice with my university's full name and tax ID? If possible, could you also send me the invoice before I make the payment?
Sorry for asking so many questions! I just want to make sure everything is ready before booking my flight.
Thanks a lot for your help!
Best regards,
Emily Johnson
PhD Student""",
}

ADV_FACT_CARD = """会议日期: June 18-20, 2027
会议地点: Chengdu, China
学生作者早鸟价: USD 280
学生作者普通价: USD 350
早鸟截止日期: May 1, 2027
学生资格: 需要有效全日制学生身份
学生证明: 学生证或正式在读证明
住宿信息: 尚未公布
酒店协议价: 未提供
酒店价格: 未提供
早餐信息: 未提供
发票政策: 未提供
发票税号要求: 未提供
付款前开票: 未提供"""

SINGLE_LABEL_PROMPT = """你是会议邮件分类器。请判断这封邮件的主意图，只能选一个：
registration_inquiry, submission_deadline, acceptance_inquiry, payment_inquiry,
accommodation_inquiry, certificate_request, paper_update_request, technical_issue, other。
输出 JSON：{"primary_intent": "...", "reason": "..."}"""

MULTI_LABEL_PROMPT = """你是会议邮件分类器。请识别这封邮件涉及的所有业务意图（多标签），
可选集合：registration_inquiry, submission_deadline, acceptance_inquiry, payment_inquiry,
accommodation_inquiry, certificate_request, paper_update_request, technical_issue, other。
同时提取发件人、用户身份、会议名称、具体问题列表、以及每个问题是否能在事实卡中回答
（known / unknown），未知项标记为待人工确认。
输出 JSON：
{
  "sender": "...",
  "user_role": "...",
  "conference_name": "...",
  "intents": ["..."],
  "questions": [{"question": "...", "status": "known|unknown", "related_fact": "..."}],
  "requires_human_review": true/false,
  "review_reasons": ["..."]
}"""

REPLY_STYLES_PROMPT = """你是会议秘书。请根据邮件、分析结果和事实卡，生成三种英文回复草稿：
- formal：正式专业
- concise：简洁高效
- friendly：友好热情
三种草稿事实内容必须一致，未知信息不得编造，需说明"尚未公布/无法确认"并建议联系秘书处。
输出 JSON：
{
  "formal":   {"subject": "...", "body": "..."},
  "concise":  {"subject": "...", "body": "..."},
  "friendly": {"subject": "...", "body": "..."}
}"""


def run():
    user_email = (f"Subject: {ADV_EMAIL['subject']}\nFrom: {ADV_EMAIL['from']}\n\n"
                  f"{ADV_EMAIL['body']}")

    print("\n==== 单标签分类 ====")
    raw_single = chat(SINGLE_LABEL_PROMPT, user_email, temperature=0.0, use_json_mode=True)
    print(raw_single)

    print("\n==== 多标签分类 + 信息提取 ====")
    raw_multi = chat(MULTI_LABEL_PROMPT,
                     user_email + "\n\n=== 事实卡 ===\n" + ADV_FACT_CARD,
                     temperature=0.0, use_json_mode=True)
    print(raw_multi)

    print("\n==== 三种风格回复 ====")
    raw_reply = chat(
        REPLY_STYLES_PROMPT,
        f"=== 邮件 ===\n{user_email}\n\n=== 分析 ===\n{raw_multi}\n\n=== 事实卡 ===\n{ADV_FACT_CARD}",
        temperature=0.3, use_json_mode=True)
    print(raw_reply)

    with open("advanced_email_results.json", "w", encoding="utf-8") as f:
        json.dump({"single": raw_single, "multi": raw_multi, "reply": raw_reply},
                  f, ensure_ascii=False, indent=2)
    print("\n结果已保存到 advanced_email_results.json")


if __name__ == "__main__":
    run()