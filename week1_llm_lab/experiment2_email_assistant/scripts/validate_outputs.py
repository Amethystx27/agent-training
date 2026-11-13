from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"


def load_runner_module() -> Any:
    path = ROOT / "scripts" / "run_base_experiment.py"
    specification = importlib.util.spec_from_file_location("base_experiment_runner", path)
    if specification is None or specification.loader is None:
        raise RuntimeError("Could not load the experiment runner module")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main() -> None:
    runner = load_runner_module()
    dataset = runner.read_json(ROOT / "data" / "base_emails.json")
    policy = runner.read_json(ROOT / "data" / "fact_audit_policy.json")
    fact_card = runner.read_json(ROOT / "data" / "iccbda_2027_fact_card.json")
    failures: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []

    for email in dataset["emails"]:
        email_id = email["email_id"]
        prefix = f"email_{email_id.lower()}"
        analysis = runner.read_json(OUTPUT_DIR / f"{prefix}_analysis.json")
        audit = runner.read_json(OUTPUT_DIR / f"{prefix}_fact_audit.json")
        reply = runner.read_json(OUTPUT_DIR / f"{prefix}_reply.json")

        try:
            runner.validate_analysis(analysis, email, policy["emails"][email_id])
        except Exception as exc:
            failures.append({"email_id": email_id, "stage": "analysis", "error": str(exc)})

        expected_audit_fields = {
            "email_id",
            "conference_name",
            "fact_card_id",
            "method",
            "all_questions_covered",
            "items",
            "requires_human_review",
            "review_reasons",
        }
        try:
            runner.require(set(audit) == expected_audit_fields, "incorrect fact audit fields")
            runner.require(audit["email_id"] == email_id, "fact audit email_id mismatch")
            runner.require(
                audit["conference_name"] == fact_card["conference_name"],
                "fact audit conference mismatch",
            )
            runner.require(audit["fact_card_id"] == fact_card["fact_card_id"], "fact card ID mismatch")
            runner.require(audit["method"] == "deterministic_fact_check", "incorrect audit method")
            runner.require(audit["all_questions_covered"] is True, "not all questions are covered")
            runner.require(
                len(audit["items"]) == len(analysis["questions"]),
                "fact audit item count does not match question count",
            )
            runner.require(
                [item["question_index"] for item in audit["items"]]
                == list(range(len(analysis["questions"]))),
                "fact audit question indexes are incomplete or out of order",
            )
            runner.require(
                all(item["question"] == analysis["questions"][item["question_index"]] for item in audit["items"]),
                "fact audit question text does not match analysis",
            )
            expected_review = any(item["requires_human_review"] for item in audit["items"])
            runner.require(
                audit["requires_human_review"] == expected_review,
                "fact audit overall review flag is incorrect",
            )
            runner.require(
                analysis["requires_human_review"] == audit["requires_human_review"],
                "analysis and fact audit review flags differ",
            )
        except Exception as exc:
            failures.append({"email_id": email_id, "stage": "fact_audit", "error": str(exc)})

        try:
            runner.validate_reply(reply, audit)
        except Exception as exc:
            failures.append({"email_id": email_id, "stage": "reply", "error": str(exc)})

        checks.append(
            {
                "email_id": email_id,
                "primary_intent": analysis["primary_intent"],
                "secondary_intents": analysis["secondary_intents"],
                "question_count": len(analysis["questions"]),
                "fact_audit_count": len(audit["items"]),
                "requires_human_review": audit["requires_human_review"],
            }
        )

    run_summary_path = OUTPUT_DIR / "run_summary.json"
    model = runner.read_json(run_summary_path)["model"] if run_summary_path.exists() else None
    report = {
        "status": "passed" if not failures else "failed",
        "model": model,
        "email_count": len(checks),
        "checks": checks,
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
