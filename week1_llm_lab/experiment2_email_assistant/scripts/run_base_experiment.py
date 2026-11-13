from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

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

ANALYSIS_FIELDS = {
    "sender",
    "subject",
    "conference_name",
    "primary_intent",
    "secondary_intents",
    "user_role",
    "questions",
    "extracted_entities",
    "requires_human_review",
    "review_reason",
}

ENTITY_FIELDS = {
    "paper_title",
    "registration_email",
    "claimed_fee",
    "payment_status_claim",
    "requested_services",
    "technical_issue",
}

REPLY_FIELDS = {
    "subject",
    "body",
    "requires_human_review",
    "review_reason",
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    if not isinstance(value, dict):
        raise ValueError("Model output must be a JSON object.")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_analysis(
    value: dict[str, Any],
    email: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    require(set(value) == ANALYSIS_FIELDS, f"Analysis fields must be exactly {sorted(ANALYSIS_FIELDS)}")
    require(value["sender"] == email["sender"], "sender does not match the source email")
    require(value["subject"] == email["subject"], "subject does not match the source email")
    require(
        value["conference_name"] == email["conference_name"],
        f"conference_name must be {email['conference_name']}",
    )
    require(value["primary_intent"] in INTENTS, "primary_intent is not an allowed category")
    require(isinstance(value["secondary_intents"], list), "secondary_intents must be an array")
    require(
        all(item in INTENTS for item in value["secondary_intents"]),
        "secondary_intents contains an invalid category",
    )
    require(
        len(value["secondary_intents"]) == len(set(value["secondary_intents"])),
        "secondary_intents contains duplicates",
    )
    require(
        value["primary_intent"] not in value["secondary_intents"],
        "secondary_intents must not repeat primary_intent",
    )
    require(
        value["primary_intent"] == policy["expected_primary_intent"],
        f"primary_intent must be {policy['expected_primary_intent']}",
    )
    require(
        set(value["secondary_intents"]) == set(policy["expected_secondary_intents"]),
        f"secondary_intents must be {policy['expected_secondary_intents']}",
    )
    require(
        value["user_role"] is None or isinstance(value["user_role"], str),
        "user_role must be a string or null",
    )
    require(isinstance(value["questions"], list), "questions must be an array")
    require(
        all(isinstance(item, str) and item.strip() for item in value["questions"]),
        "questions must contain non-empty strings",
    )
    require(
        len(value["questions"]) == policy["expected_question_count"],
        f"questions must contain {policy['expected_question_count']} items",
    )
    entities = value["extracted_entities"]
    require(isinstance(entities, dict), "extracted_entities must be an object")
    require(set(entities) == ENTITY_FIELDS, f"extracted_entities fields must be exactly {sorted(ENTITY_FIELDS)}")
    for scalar_key in (
        "paper_title",
        "registration_email",
        "claimed_fee",
        "payment_status_claim",
        "technical_issue",
    ):
        require(
            entities[scalar_key] is None or isinstance(entities[scalar_key], str),
            f"extracted_entities.{scalar_key} must be a string or null",
        )
    require(isinstance(entities["requested_services"], list), "requested_services must be an array")
    require(
        all(isinstance(item, str) and item.strip() for item in entities["requested_services"]),
        "requested_services must contain non-empty strings",
    )
    require(isinstance(value["requires_human_review"], bool), "requires_human_review must be boolean")
    expected_review = any(item["requires_human_review"] for item in policy["items"])
    require(
        value["requires_human_review"] == expected_review,
        f"requires_human_review must be {str(expected_review).lower()} for this email",
    )
    if value["requires_human_review"]:
        require(
            isinstance(value["review_reason"], str) and value["review_reason"].strip(),
            "review_reason must be non-empty when human review is required",
        )
    else:
        require(value["review_reason"] is None, "review_reason must be null when human review is not required")
    return value


def build_fact_audit(
    email: dict[str, Any],
    analysis: dict[str, Any],
    policy: dict[str, Any],
    fact_card: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for configured_item in policy["items"]:
        question_index = configured_item["question_index"]
        items.append(
            {
                "question_index": question_index,
                "question": analysis["questions"][question_index],
                "topic": configured_item["topic"],
                "status": configured_item["status"],
                "fact_reference": configured_item["fact_reference"],
                "evidence": configured_item["evidence"],
                "requires_human_review": configured_item["requires_human_review"],
                "review_reason": configured_item["review_reason"],
                "response_guidance": configured_item["response_guidance"],
            }
        )
    review_reasons = list(
        dict.fromkeys(
            item["review_reason"]
            for item in items
            if item["requires_human_review"] and item["review_reason"]
        )
    )
    return {
        "email_id": email["email_id"],
        "conference_name": email["conference_name"],
        "fact_card_id": fact_card["fact_card_id"],
        "method": "deterministic_fact_check",
        "all_questions_covered": len(items) == len(analysis["questions"]),
        "items": items,
        "requires_human_review": any(item["requires_human_review"] for item in items),
        "review_reasons": review_reasons,
    }


def validate_reply(
    value: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    require(set(value) == REPLY_FIELDS, f"Reply fields must be exactly {sorted(REPLY_FIELDS)}")
    require(isinstance(value["subject"], str) and value["subject"].strip(), "subject must be non-empty")
    require(isinstance(value["body"], str) and value["body"].strip(), "body must be non-empty")
    require(isinstance(value["requires_human_review"], bool), "requires_human_review must be boolean")
    require(
        value["requires_human_review"] == audit["requires_human_review"],
        "reply review flag does not match the fact audit",
    )
    if value["requires_human_review"]:
        require(
            isinstance(value["review_reason"], str) and value["review_reason"].strip(),
            "review_reason must be non-empty when human review is required",
        )
        require(
            "[HUMAN REVIEW REQUIRED]" in value["body"],
            "review body must contain the [HUMAN REVIEW REQUIRED] marker",
        )
    else:
        require(value["review_reason"] is None, "review_reason must be null when review is not required")
        require(
            "[HUMAN REVIEW REQUIRED]" not in value["body"],
            "review marker must not appear when review is not required",
        )
    return value


class JsonModelRunner:
    def __init__(self, client: OpenAI, model: str, call_log: list[dict[str, Any]]) -> None:
        self.client = client
        self.model = model
        self.call_log = call_log

    def run(
        self,
        stage: str,
        email_id: str,
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
                    max_tokens=2500,
                    response_format={"type": "json_object"},
                )
                elapsed = round(time.monotonic() - started, 3)
                content = response.choices[0].message.content or ""
                usage = None
                if response.usage is not None:
                    usage = response.usage.model_dump()
                parsed = parse_json_object(content)
                validated = validator(parsed)
                self.call_log.append(
                    {
                        "email_id": email_id,
                        "stage": stage,
                        "attempt": attempt,
                        "duration_seconds": elapsed,
                        "usage": usage,
                        "success": True,
                    }
                )
                return validated
            except Exception as exc:
                elapsed = round(time.monotonic() - started, 3)
                last_error = str(exc)
                self.call_log.append(
                    {
                        "email_id": email_id,
                        "stage": stage,
                        "attempt": attempt,
                        "duration_seconds": elapsed,
                        "usage": None,
                        "success": False,
                        "error": last_error,
                    }
                )
                if attempt < 3:
                    retry_messages = list(messages)
                    if content:
                        retry_messages.append({"role": "assistant", "content": content})
                    retry_messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous answer failed validation: "
                                + last_error
                                + "\nReturn the complete corrected JSON object now."
                            ),
                        }
                    )
                    working_messages = retry_messages
                    time.sleep(attempt)
        raise RuntimeError(f"{stage} failed for email {email_id}: {last_error}")


def write_fact_audit_markdown(
    path: Path,
    audits: list[dict[str, Any]],
) -> None:
    lines = [
        "# 基础实验事实核验汇总",
        "",
        "| 邮件 | 问题 | 核验状态 | 事实依据 | 人工审核 |",
        "|---|---|---|---|---|",
    ]
    for audit in audits:
        for item in audit["items"]:
            question = item["question"].replace("|", "\\|")
            evidence = (item["evidence"] or "事实卡未提供").replace("|", "\\|")
            review = "是" if item["requires_human_review"] else "否"
            lines.append(
                f"| {audit['email_id']} | {question} | {item['status']} | {evidence} | {review} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_replies_markdown(
    path: Path,
    emails: list[dict[str, Any]],
    replies: dict[str, dict[str, Any]],
) -> None:
    lines = ["# 基础实验英文回复草稿", ""]
    for email in emails:
        email_id = email["email_id"]
        reply = replies[email_id]
        lines.extend(
            [
                f"## Email {email_id}",
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

    dataset = read_json(DATA_DIR / "base_emails.json")
    fact_card = read_json(DATA_DIR / "iccbda_2027_fact_card.json")
    audit_policy = read_json(DATA_DIR / "fact_audit_policy.json")
    analysis_prompt = (PROMPT_DIR / "analysis_system.md").read_text(encoding="utf-8")
    reply_prompt = (PROMPT_DIR / "reply_system.md").read_text(encoding="utf-8")
    require(dataset["email_count"] == 6, "Base dataset must contain six emails")
    require(
        [email["email_id"] for email in dataset["emails"]] == list("ABCDEF"),
        "Base dataset email order must be A-F",
    )

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)
    calls: list[dict[str, Any]] = []
    runner = JsonModelRunner(client, model, calls)
    started_at = utc_now()
    audits: list[dict[str, Any]] = []
    replies: dict[str, dict[str, Any]] = {}
    output_files: list[str] = []

    summary: dict[str, Any] = {
        "status": "running",
        "model": model,
        "base_url_host": urlparse(base_url).hostname,
        "temperature": 0,
        "started_at": started_at,
        "completed_at": None,
        "email_count": len(dataset["emails"]),
        "calls": calls,
        "output_files": output_files,
        "prompt_sha256": {
            "analysis": file_sha256(PROMPT_DIR / "analysis_system.md"),
            "reply": file_sha256(PROMPT_DIR / "reply_system.md"),
        },
    }

    try:
        for email in dataset["emails"]:
            email_id = email["email_id"]
            policy = audit_policy["emails"][email_id]
            print(f"[analysis] Email {email_id}")
            analysis_messages = [
                {
                    "role": "system",
                    "content": analysis_prompt.replace(
                        "{{FACT_CARD}}",
                        json.dumps(fact_card, ensure_ascii=False, indent=2),
                    ).replace(
                        "{{EMAIL}}",
                        json.dumps(email, ensure_ascii=False, indent=2),
                    ),
                }
            ]
            analysis = runner.run(
                "analysis",
                email_id,
                analysis_messages,
                lambda value, email=email, policy=policy: validate_analysis(
                    value, email, policy
                ),
            )
            analysis_path = OUTPUT_DIR / f"email_{email_id.lower()}_analysis.json"
            write_json(analysis_path, analysis)
            output_files.append(str(analysis_path.relative_to(ROOT)))

            print(f"[fact_audit] Email {email_id}")
            audit = build_fact_audit(email, analysis, policy, fact_card)
            require(audit["all_questions_covered"], f"fact audit did not cover all questions for {email_id}")
            audit_path = OUTPUT_DIR / f"email_{email_id.lower()}_fact_audit.json"
            write_json(audit_path, audit)
            audits.append(audit)
            output_files.append(str(audit_path.relative_to(ROOT)))

            print(f"[reply] Email {email_id}")
            reply_messages = [
                {
                    "role": "system",
                    "content": reply_prompt.replace(
                        "{{FACT_CARD}}",
                        json.dumps(fact_card, ensure_ascii=False, indent=2),
                    )
                    .replace(
                        "{{EMAIL}}",
                        json.dumps(email, ensure_ascii=False, indent=2),
                    )
                    .replace(
                        "{{ANALYSIS}}",
                        json.dumps(analysis, ensure_ascii=False, indent=2),
                    )
                    .replace(
                        "{{AUDIT}}",
                        json.dumps(audit, ensure_ascii=False, indent=2),
                    ),
                }
            ]
            reply = runner.run(
                "reply",
                email_id,
                reply_messages,
                lambda value, audit=audit: validate_reply(value, audit),
            )
            reply_path = OUTPUT_DIR / f"email_{email_id.lower()}_reply.json"
            write_json(reply_path, reply)
            replies[email_id] = reply
            output_files.append(str(reply_path.relative_to(ROOT)))

        write_fact_audit_markdown(OUTPUT_DIR / "fact_audit_summary.md", audits)
        write_replies_markdown(OUTPUT_DIR / "draft_replies.md", dataset["emails"], replies)
        output_files.extend(
            [
                str((OUTPUT_DIR / "fact_audit_summary.md").relative_to(ROOT)),
                str((OUTPUT_DIR / "draft_replies.md").relative_to(ROOT)),
            ]
        )
        summary["status"] = "completed"
        summary["completed_at"] = utc_now()
        summary["human_review_emails"] = [
            audit["email_id"] for audit in audits if audit["requires_human_review"]
        ]
        summary["call_count"] = len(calls)
        summary["failed_call_attempts"] = sum(1 for call in calls if not call["success"])
        usage_totals: Counter[str] = Counter()
        for call in calls:
            usage = call.get("usage") or {}
            for key, value in usage.items():
                if isinstance(value, int):
                    usage_totals[key] += value
        summary["usage_totals"] = dict(usage_totals)
    except Exception as exc:
        summary["status"] = "failed"
        summary["completed_at"] = utc_now()
        summary["error"] = str(exc).replace(api_key, "[REDACTED]")
        raise
    finally:
        summary_path = str((OUTPUT_DIR / "run_summary.json").relative_to(ROOT))
        if summary_path not in output_files:
            output_files.append(summary_path)
        for call in calls:
            if "error" in call:
                call["error"] = str(call["error"]).replace(api_key, "[REDACTED]")
        write_json(OUTPUT_DIR / "run_summary.json", summary)
        print(f"[run_summary] {summary['status']}")


if __name__ == "__main__":
    main()
