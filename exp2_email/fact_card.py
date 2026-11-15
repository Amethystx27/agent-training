FACT_CARD = {
    "conference_name": "ICCBDA 2027",
    "conference_dates": "May 21–23, 2027",
    "location": "Xihua University, Chengdu, China",
    "submission_deadline": "February 15, 2027",
    "fee_student_author": "USD 350",
    "fee_regular_author": "USD 450",
    "fee_listener": "USD 180",
    "accommodation": "尚未公布，请关注会议官方通知",
    "acceptance_result": "只能通过投稿系统查询；邮件中不提供个人录用结论",
    "refund_policy": "未提供正式政策，必须转人工确认",
    "contact_email": "iccbda2027@example.org",
}

FACT_CARD_TEXT = "\n".join(f"- {k}: {v}" for k, v in FACT_CARD.items())

INTENT_CATEGORIES = [
    "registration_inquiry", "submission_deadline", "acceptance_inquiry",
    "payment_inquiry", "accommodation_inquiry", "certificate_request",
    "paper_update_request", "technical_issue", "other",
]

HUMAN_REVIEW_INTENTS = {"acceptance_inquiry", "payment_inquiry",
                        "paper_update_request"}