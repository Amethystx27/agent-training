from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT.parent / ".env"
DATA_DIR = ROOT / "data"
PROMPT_DIR = ROOT / "prompts"
OUTPUT_DIR = ROOT / "outputs"

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

STYLE_DESCRIPTIONS = {
    "formal": "Formal: complete sentences, formal salutation and closing, professional and precise.",
    "concise": "Concise: short and direct paragraphs or bullets while retaining all required facts.",
    "friendly": "Friendly: warm and approachable while remaining professional and factually identical.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    require(isinstance(value, dict), "model output must be a JSON object")
    return value


class JsonModelRunner:
    def __init__(self, client: OpenAI, model: str) -> None:
        self.client = client
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        stage: str,
        messages: list[dict[str, str]],
        validator: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        working_messages = list(messages)
        last_error = ""
        for attempt in range(1, 4):
            started = time.monotonic()
            content = ""
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=working_messages,
                    temperature=0,
                    max_tokens=4000,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or ""
                parsed = parse_json_object(content)
                validated = validator(parsed)
                usage = response.usage.model_dump() if response.usage is not None else None
                self.calls.append(
                    {
                        "stage": stage,
                        "attempt": attempt,
                        "success": True,
                        "duration_seconds": round(time.monotonic() - started, 3),
                        "usage": usage,
                    }
                )
                return validated
            except Exception as exc:
                last_error = str(exc)
                self.calls.append(
                    {
                        "stage": stage,
                        "attempt": attempt,
                        "success": False,
                        "duration_seconds": round(time.monotonic() - started, 3),
                        "error": last_error,
                    }
                )
                if attempt < 3:
                    retry = list(messages)
                    if content:
                        retry.append({"role": "assistant", "content": content})
                    retry.append(
                        {
                            "role": "user",
                            "content": (
                                "The previous answer failed validation: "
                                + last_error
                                + "\nReturn the complete corrected JSON object now."
                            ),
                        }
                    )
                    working_messages = retry
                    time.sleep(attempt)
        raise RuntimeError(f"{stage} failed: {last_error}")


def validate_single_label(
    value: dict[str, Any],
    email: dict[str, Any],
) -> dict[str, Any]:
    require(
        set(value) == {"email_id", "method", "predicted_intent", "reason"},
        "single-label fields are incorrect",
    )
    require(value["email_id"] == email["email_id"], "single-label email_id mismatch")
    require(value["method"] == "single_label", "single-label method mismatch")
    require(value["predicted_intent"] in INTENTS, "single-label intent is invalid")
    require(isinstance(value["reason"], str) and value["reason"].strip(), "single-label reason is missing")
    return value


def validate_multi_label(
    value: dict[str, Any],
    email: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "email_id",
        "method",
        "primary_intent",
        "secondary_intents",
        "intents",
        "business_intents",
        "reason",
    }
    require(set(value) == fields, "multi-label fields are incorrect")
    require(value["email_id"] == email["email_id"], "multi-label email_id mismatch")
    require(value["method"] == "multi_label", "multi-label method mismatch")
    require(value["primary_intent"] == "registration_inquiry", "multi-label primary intent is incorrect")
    require(
        set(value["secondary_intents"]) == {"accommodation_inquiry", "payment_inquiry"},
        "multi-label secondary intents are incomplete",
    )
    require(
        set(value["intents"]) == {"registration_inquiry", "accommodation_inquiry", "payment_inquiry"},
        "multi-label intents are incomplete",
    )
    require(
        set(value["business_intents"])
        == {"registration_inquiry", "accommodation_inquiry", "invoice_request"},
        "multi-label business_intents must be exactly registration_inquiry, accommodation_inquiry, "
        f"invoice_request; got {value['business_intents']}",
    )
    require(isinstance(value["reason"], str) and value["reason"].strip(), "multi-label reason is missing")
    return value


def validate_extraction(
    value: dict[str, Any],
    email: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "email_id",
        "subject",
        "sender",
        "recipient",
        "conference_name",
        "user_role",
        "questions",
        "extracted_entities",
        "requires_human_review",
        "review_reason",
    }
    require(set(value) == fields, "extraction fields are incorrect")
    require(value["email_id"] == "G", "extraction email_id mismatch")
    require(value["subject"] == email["subject"], "extraction subject mismatch")
    require(value["sender"] == email["sender"], "extraction sender mismatch")
    require(value["recipient"] == email["recipient"], "extraction recipient mismatch")
    require(value["conference_name"] == email["conference_name"], "extraction conference mismatch")
    require("phd" in value["user_role"].lower(), "user_role must retain the PhD student claim")
    require(isinstance(value["questions"], list) and len(value["questions"]) == 10, "exactly 10 questions are required")
    areas = []
    for question in value["questions"]:
        require(
            set(question) == {"id", "business_area", "text", "request_type"},
            "question fields are incorrect",
        )
        require(question["business_area"] in {"registration", "accommodation", "invoice"}, "question area is invalid")
        require(question["request_type"] in {"question", "preference", "request"}, "request_type is invalid")
        require(isinstance(question["text"], str) and question["text"].strip(), "question text is empty")
        areas.append(question["business_area"])
    require(areas == policy["expected_question_areas"], "question areas or order are incorrect")

    entities = value["extracted_entities"]
    entity_fields = {
        "paper_presentation_claim",
        "student_status_claim",
        "quoted_early_bird_fee",
        "payment_timing",
        "accommodation_preferences",
        "invoice_requirements",
        "language_notes",
    }
    require(set(entities) == entity_fields, "extracted entity fields are incorrect")
    require("present" in entities["paper_presentation_claim"].lower(), "paper presentation claim is missing")
    require("phd" in entities["student_status_claim"].lower(), "student status claim is missing")
    require("280" in entities["quoted_early_bird_fee"], "quoted early-bird fee is missing")
    require("next week" in entities["payment_timing"].lower(), "payment timing is missing")
    require(
        any("walk" in item.lower() for item in entities["accommodation_preferences"]),
        "walking-distance preference is missing",
    )
    require(
        any("discount" in item.lower() for item in entities["accommodation_preferences"]),
        "conference discount preference is missing",
    )
    require(
        any("tax" in item.lower() for item in entities["invoice_requirements"]),
        "invoice tax-ID requirement is missing",
    )
    require(
        any("payment" in item.lower() for item in entities["invoice_requirements"]),
        "pre-payment invoice request is missing",
    )
    require(
        any("recomm" in item.lower() for item in entities["language_notes"]),
        "misspelling was not noted",
    )
    require(value["requires_human_review"] is True, "invoice request must require human review")
    require(
        isinstance(value["review_reason"], str) and value["review_reason"].strip(),
        "extraction review reason is missing",
    )
    return value


def build_fact_audit(
    extraction: dict[str, Any],
    policy: dict[str, Any],
    fact_card: dict[str, Any],
) -> dict[str, Any]:
    items = []
    for configured in policy["items"]:
        index = configured["question_index"]
        question = extraction["questions"][index]
        items.append(
            {
                "question_index": index,
                "question": question["text"],
                "business_area": question["business_area"],
                "topic": configured["topic"],
                "status": configured["status"],
                "fact_reference": configured["fact_reference"],
                "evidence": configured["evidence"],
                "requires_human_review": configured["requires_human_review"],
                "review_reason": configured["review_reason"],
                "response_guidance": configured["response_guidance"],
            }
        )
    status_counts = Counter(item["status"] for item in items)
    review_reasons = list(
        dict.fromkeys(
            item["review_reason"]
            for item in items
            if item["requires_human_review"] and item["review_reason"]
        )
    )
    return {
        "email_id": "G",
        "conference_name": fact_card["conference_name"],
        "fact_card_id": fact_card["fact_card_id"],
        "method": "deterministic_fact_check",
        "all_questions_covered": len(items) == len(extraction["questions"]),
        "items": items,
        "known_count": status_counts["supported"],
        "conditional_count": status_counts["conditional"],
        "unknown_count": status_counts["unknown"],
        "requires_human_review": any(item["requires_human_review"] for item in items),
        "review_reasons": review_reasons,
    }


def validate_reply(
    value: dict[str, Any],
    style: str,
) -> dict[str, Any]:
    fields = {
        "style",
        "subject",
        "body",
        "requires_human_review",
        "review_reason",
        "facts_used",
        "unknown_items",
    }
    require(set(value) == fields, "reply fields are incorrect")
    require(
        isinstance(value["style"], str) and value["style"].lower() == style,
        f"reply style must be {style}",
    )
    value["style"] = style
    require(isinstance(value["subject"], str) and value["subject"].strip(), "reply subject is empty")
    body = value["body"]
    require(isinstance(body, str) and body.strip(), "reply body is empty")
    require(value["requires_human_review"] is True, "invoice reply must require human review")
    require(
        isinstance(value["review_reason"], str) and value["review_reason"].strip(),
        "reply review reason is missing",
    )
    require("[HUMAN REVIEW REQUIRED]" in body, "reply is missing the human-review marker")
    lower = body.lower()
    require("usd 280" in lower, "reply does not state the USD 280 fee")
    require("may 1, 2027" in lower, "reply does not state the early-bird deadline")
    require("full-time" in lower, "reply does not state full-time eligibility")
    require(
        "student id" in lower or "enrollment certificate" in lower,
        "reply does not state acceptable student proof",
    )
    require("next week" in lower, "reply does not address next-week payment")
    require(
        "hotel" in lower or "accommodation" in lower,
        "reply does not address accommodation",
    )
    require("invoice" in lower, "reply does not address the invoice request")
    require(
        "not yet been announced" in lower or "not announced yet" in lower,
        "reply does not clearly state that accommodation is not announced",
    )
    require(
        "not currently available" in lower or "not available" in lower,
        "reply does not clearly state unavailable information",
    )
    amounts = {int(value.replace(",", "")) for value in re.findall(r"USD\s*([0-9][0-9,]*)", body, re.IGNORECASE)}
    require(amounts <= {280, 350}, "reply contains an unsupported USD amount")
    require(
        re.search(r"we (will|can) (guarantee|issue).*invoice", lower) is None,
        "reply appears to promise an invoice",
    )
    require(isinstance(value["facts_used"], list) and value["facts_used"], "facts_used is empty")
    require(isinstance(value["unknown_items"], list) and value["unknown_items"], "unknown_items is empty")
    return value


def build_comparison(
    single: dict[str, Any],
    multi: dict[str, Any],
) -> dict[str, Any]:
    expected = [
        "registration_inquiry",
        "accommodation_inquiry",
        "invoice_request",
    ]
    mapping = {
        "registration_inquiry": "registration_inquiry",
        "accommodation_inquiry": "accommodation_inquiry",
        "payment_inquiry": "invoice_request",
    }
    single_business = [mapping[single["predicted_intent"]]] if single["predicted_intent"] in mapping else []
    multi_business = multi["business_intents"]
    single_missed = [intent for intent in expected if intent not in single_business]
    multi_missed = [intent for intent in expected if intent not in multi_business]
    return {
        "email_id": "G",
        "expected_business_intents": expected,
        "single_label": {
            "predicted_intent": single["predicted_intent"],
            "identified_business_intents": single_business,
            "missed_business_intents": single_missed,
            "intent_coverage": round(len(single_business) / len(expected), 4),
        },
        "multi_label": {
            "category_intents": multi["intents"],
            "identified_business_intents": multi_business,
            "missed_business_intents": multi_missed,
            "intent_coverage": round(len(multi_business) / len(expected), 4),
        },
        "conclusion": "单标签分类只识别出一个业务主题，遗漏了同一封邮件中的住宿和发票请求；多标签分类完整覆盖注册、住宿和发票三类业务意图。",
    }


def write_comparison_markdown(path: Path, comparison: dict[str, Any]) -> None:
    single = comparison["single_label"]
    multi = comparison["multi_label"]
    lines = [
        "# 进阶邮件单标签与多标签分类比较",
        "",
        "| 方法 | 识别业务意图 | 漏检业务意图 | 覆盖率 |",
        "|---|---|---|---:|",
        (
            f"| 单标签 | {', '.join(single['identified_business_intents']) or '无'} | "
            f"{', '.join(single['missed_business_intents']) or '无'} | "
            f"{single['intent_coverage']:.0%} |"
        ),
        (
            f"| 多标签 | {', '.join(multi['identified_business_intents'])} | "
            f"{', '.join(multi['missed_business_intents']) or '无'} | "
            f"{multi['intent_coverage']:.0%} |"
        ),
        "",
        "## 分析",
        "",
        comparison["conclusion"],
        "",
        "单标签方法会压缩邮件中并列的业务主题，适合只记录一个工单主类别的场景；多标签方法更适合跨部门协作的复杂咨询邮件。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_replies_markdown(path: Path, replies: dict[str, Any]) -> None:
    lines = ["# AIIoT 2027 进阶邮件三风格回复", ""]
    for style in ("formal", "concise", "friendly"):
        reply = replies["replies"][style]
        lines.extend(
            [
                f"## {style.title()}",
                "",
                f"**Subject:** {reply['subject']}",
                "",
                reply["body"].strip(),
                "",
                f"**Human review:** {reply['requires_human_review']}",
                "",
                f"**Review reason:** {reply['review_reason']}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    env = load_env(ENV_PATH)
    api_key = env.get("OPENAI_API_KEY", "")
    base_url = env.get("OPENAI_BASE_URL", "")
    model = env.get("MODEL_NAME", "")
    require(bool(api_key), "OPENAI_API_KEY is missing")
    require(bool(base_url), "OPENAI_BASE_URL is missing")
    require(bool(model), "MODEL_NAME is missing")

    email = read_json(DATA_DIR / "advanced_email_g.json")
    fact_card = read_json(DATA_DIR / "aiiot_2027_fact_card.json")
    policy = read_json(DATA_DIR / "advanced_fact_audit_policy.json")
    prompts = {
        name: (PROMPT_DIR / name).read_text(encoding="utf-8")
        for name in (
            "advanced_single_label.md",
            "advanced_multi_label.md",
            "advanced_extraction.md",
            "advanced_reply.md",
        )
    }

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
    runner = JsonModelRunner(client, model)
    fact_text = json.dumps(fact_card, ensure_ascii=False, indent=2)
    email_text = json.dumps(email, ensure_ascii=False, indent=2)

    print("[advanced] single-label classification")
    single = runner.run(
        "single_label",
        [
            {
                "role": "system",
                "content": prompts["advanced_single_label.md"]
                .replace("{{FACT_CARD}}", fact_text)
                .replace("{{EMAIL}}", email_text),
            }
        ],
        lambda value: validate_single_label(value, email),
    )
    write_json(OUTPUT_DIR / "advanced_single_label.json", single)

    print("[advanced] multi-label classification")
    multi = runner.run(
        "multi_label",
        [
            {
                "role": "system",
                "content": prompts["advanced_multi_label.md"]
                .replace("{{FACT_CARD}}", fact_text)
                .replace("{{EMAIL}}", email_text),
            }
        ],
        lambda value: validate_multi_label(value, email),
    )
    write_json(OUTPUT_DIR / "advanced_multi_label.json", multi)

    print("[advanced] information extraction")
    extraction = runner.run(
        "extraction",
        [
            {
                "role": "system",
                "content": prompts["advanced_extraction.md"].replace("{{EMAIL}}", email_text),
            }
        ],
        lambda value: validate_extraction(value, email, policy),
    )
    write_json(OUTPUT_DIR / "advanced_extraction.json", extraction)

    print("[advanced] deterministic fact audit")
    audit = build_fact_audit(extraction, policy, fact_card)
    require(audit["all_questions_covered"], "fact audit does not cover all questions")
    write_json(OUTPUT_DIR / "advanced_fact_audit.json", audit)

    replies: dict[str, dict[str, Any]] = {}
    for style in ("formal", "concise", "friendly"):
        print(f"[advanced] {style} reply")
        replies[style] = runner.run(
            f"reply_{style}",
            [
                {
                    "role": "system",
                    "content": prompts["advanced_reply.md"]
                    .replace("{{STYLE}}", STYLE_DESCRIPTIONS[style])
                    .replace("{{FACT_CARD}}", fact_text)
                    .replace("{{EMAIL}}", email_text)
                    .replace("{{AUDIT}}", json.dumps(audit, ensure_ascii=False, indent=2)),
                }
            ],
            lambda value, style=style: validate_reply(value, style),
        )

    reply_bundle = {
        "email_id": "G",
        "conference_name": "AIIoT 2027",
        "replies": replies,
    }
    write_json(OUTPUT_DIR / "advanced_replies.json", reply_bundle)
    write_replies_markdown(OUTPUT_DIR / "advanced_draft_replies.md", reply_bundle)

    comparison = build_comparison(single, multi)
    write_json(OUTPUT_DIR / "advanced_classification_comparison.json", comparison)
    write_comparison_markdown(
        OUTPUT_DIR / "advanced_classification_comparison.md",
        comparison,
    )

    failed_attempts = sum(1 for call in runner.calls if not call["success"])
    total_tokens = sum(
        (call.get("usage") or {}).get("total_tokens", 0)
        for call in runner.calls
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "model": model,
                "email_id": "G",
                "call_attempts": len(runner.calls),
                "failed_attempts": failed_attempts,
                "total_tokens": total_tokens,
                "human_review_required": audit["requires_human_review"],
                "single_label": single["predicted_intent"],
                "multi_label": multi["intents"],
                "completed_at": utc_now(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
