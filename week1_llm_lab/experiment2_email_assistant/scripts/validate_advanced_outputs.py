from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"


def load_runner() -> Any:
    path = ROOT / "scripts" / "run_advanced_experiment.py"
    specification = importlib.util.spec_from_file_location("advanced_experiment_runner", path)
    if specification is None or specification.loader is None:
        raise RuntimeError("Could not load advanced runner")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main() -> None:
    runner = load_runner()
    email = runner.read_json(ROOT / "data" / "advanced_email_g.json")
    fact_card = runner.read_json(ROOT / "data" / "aiiot_2027_fact_card.json")
    policy = runner.read_json(ROOT / "data" / "advanced_fact_audit_policy.json")
    single = runner.read_json(OUTPUT_DIR / "advanced_single_label.json")
    multi = runner.read_json(OUTPUT_DIR / "advanced_multi_label.json")
    extraction = runner.read_json(OUTPUT_DIR / "advanced_extraction.json")
    audit = runner.read_json(OUTPUT_DIR / "advanced_fact_audit.json")
    replies = runner.read_json(OUTPUT_DIR / "advanced_replies.json")
    comparison = runner.read_json(OUTPUT_DIR / "advanced_classification_comparison.json")
    failures: list[dict[str, str]] = []

    try:
        runner.validate_single_label(single, email)
    except Exception as exc:
        failures.append({"stage": "single_label", "error": str(exc)})
    try:
        runner.validate_multi_label(multi, email)
    except Exception as exc:
        failures.append({"stage": "multi_label", "error": str(exc)})
    try:
        runner.validate_extraction(extraction, email, policy)
    except Exception as exc:
        failures.append({"stage": "extraction", "error": str(exc)})
    try:
        expected_audit = runner.build_fact_audit(extraction, policy, fact_card)
        runner.require(audit == expected_audit, "fact audit differs from the deterministic policy result")
        runner.require(audit["known_count"] == 1, "known_count must be 1")
        runner.require(audit["conditional_count"] == 2, "conditional_count must be 2")
        runner.require(audit["unknown_count"] == 7, "unknown_count must be 7")
        runner.require(audit["requires_human_review"] is True, "overall human review must be true")
    except Exception as exc:
        failures.append({"stage": "fact_audit", "error": str(exc)})

    try:
        runner.require(set(replies) == {"email_id", "conference_name", "replies"}, "reply bundle fields are incorrect")
        runner.require(replies["email_id"] == "G", "reply bundle email_id mismatch")
        runner.require(replies["conference_name"] == "AIIoT 2027", "reply bundle conference mismatch")
        runner.require(
            set(replies["replies"]) == {"formal", "concise", "friendly"},
            "reply styles are incomplete",
        )
        for style in ("formal", "concise", "friendly"):
            runner.validate_reply(replies["replies"][style], style)
        bodies = [replies["replies"][style]["body"] for style in ("formal", "concise", "friendly")]
        runner.require(len(set(bodies)) == 3, "three style bodies must differ")
        runner.require("- " in replies["replies"]["concise"]["body"], "concise reply should use compact bullets")
        runner.require(
            "happy" in replies["replies"]["friendly"]["body"].lower()
            or "reaching out" in replies["replies"]["friendly"]["body"].lower(),
            "friendly reply should use a warmer tone",
        )
    except Exception as exc:
        failures.append({"stage": "replies", "error": str(exc)})

    try:
        expected_comparison = runner.build_comparison(single, multi)
        runner.require(comparison == expected_comparison, "classification comparison is inconsistent")
        runner.require(
            comparison["single_label"]["intent_coverage"] < comparison["multi_label"]["intent_coverage"],
            "multi-label coverage should exceed single-label coverage",
        )
    except Exception as exc:
        failures.append({"stage": "comparison", "error": str(exc)})

    report = {
        "status": "passed" if not failures else "failed",
        "email_id": "G",
        "styles": sorted(replies.get("replies", {})),
        "question_count": len(extraction.get("questions", [])),
        "fact_audit_count": len(audit.get("items", [])),
        "known_count": audit.get("known_count"),
        "conditional_count": audit.get("conditional_count"),
        "unknown_count": audit.get("unknown_count"),
        "single_label": single.get("predicted_intent"),
        "multi_label_intents": multi.get("intents"),
        "single_label_coverage": comparison.get("single_label", {}).get("intent_coverage"),
        "multi_label_coverage": comparison.get("multi_label", {}).get("intent_coverage"),
        "requires_human_review": audit.get("requires_human_review"),
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
