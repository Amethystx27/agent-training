import json
from .emails import EMAILS
from .assistant import analyze_email, draft_reply


def process_one(email: dict):
    print(f"\n{'='*70}\n邮件 {email['id']}: {email['subject']}\n{'='*70}")
    analysis = analyze_email(email["subject"], email["from"], email["body"])
    if analysis is None:
        print("分析失败，跳过")
        return None
    print("\n---- 分析结果 ----")
    print(json.dumps(analysis.model_dump(), ensure_ascii=False, indent=2))

    reply = draft_reply(email["subject"], email["from"], email["body"], analysis)
    if reply is None:
        print("回复草稿生成失败")
        return {"email": email, "analysis": analysis, "reply": None}
    print("\n---- 回复草稿 ----")
    print("Subject:", reply.subject)
    print(reply.body)
    print(f"\n[HUMAN REVIEW: {reply.requires_human_review}] {reply.review_reason or ''}")
    return {"email": email, "analysis": analysis, "reply": reply}


def main():
    results = []
    for e in EMAILS:
        results.append(process_one(e))

    out = []
    for r in results:
        if r is None:
            continue
        out.append({
            "email_id": r["email"]["id"],
            "analysis": r["analysis"].model_dump() if r["analysis"] else None,
            "reply": r["reply"].model_dump() if r["reply"] else None,
        })
    with open("email_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n结果已保存到 email_results.json")


if __name__ == "__main__":
    main()