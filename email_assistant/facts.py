# ICCBDA 2027 事实卡（实验主样本）
ICCBDA_FACTS = {
    "conference_name": "ICCBDA 2027",
    "conference_dates": "May 21-23, 2027",
    "location": "Xihua University, Chengdu, China",
    "submission_deadline": "February 15, 2027",
    "registration_fee": {
        "Student Author": "USD 350",
        "Regular Author": "USD 450",
        "Listener": "USD 180",
    },
    "accommodation": "Not yet announced. Please watch the official conference notice.",
    "acceptance_result": "Can only be checked via the submission system; personal decisions are not provided by email.",
    "refund_policy": "No official policy available; must be escalated to the secretariat for manual confirmation.",
    "contact_email": "iccbda2027@example.org",
}

# AIIoT 2027 事实卡（进阶挑战，依据实验1 CFP 通知）
AIIOT_FACTS = {
    "conference_name": "AIIoT 2027",
    "conference_full_name": "The International Conference on Artificial Intelligence and Internet of Things",
    "conference_dates": "June 18-20, 2027",
    "location": "Chengdu, China",
    "submission_deadline": "March 15, 2027",
    "acceptance_notification": "April 20, 2027",
    "camera_ready": "May 10, 2027",
    "early_bird_deadline": "May 1, 2027",
    "registration_fee": {
        "Regular Author":   {"early_bird": "USD 400", "regular": "USD 500"},
        "Student Author":   {"early_bird": "USD 280", "regular": "USD 350"},
        "Non-author Participant": {"early_bird": "USD 200", "regular": "USD 260"},
    },
    "student_eligibility": "Available only to participants with valid full-time student status; a valid student ID or official enrollment certificate is required.",
    "early_bird_condition": "Applies only to registrations with successful payment received before May 1, 2027.",
    "included_services": "Access to all technical sessions, conference materials, coffee breaks, and lunches. Accommodation and travel are NOT included.",
    "accommodation": "Not provided in the official information. Must be marked as to-be-confirmed; do NOT recommend hotels or prices.",
    "invoice_policy": "Not specified in the official information. Must be escalated to the secretariat for manual confirmation.",
    "contact_email": "registration@aiiot2027.example.org",
    "website": "www.aiiot2027.example.org",
}


def facts_to_text(facts: dict) -> str:
    """把事实卡转成 Prompt 里的可读文本。"""
    lines = []
    for k, v in facts.items():
        if isinstance(v, dict):
            lines.append(f"- {k}:")
            for kk, vv in v.items():
                if isinstance(vv, dict):
                    lines.append(f"    - {kk}: early_bird={vv.get('early_bird')}, regular={vv.get('regular')}")
                else:
                    lines.append(f"    - {kk}: {vv}")
        else:
            lines.append(f"- {k}: {v}")
    return "\n".join(lines)