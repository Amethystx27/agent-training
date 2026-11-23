from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from langchain_core.documents import Document


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import rag_experiment3 as exp3  # noqa: E402


class RagExperimentThreeTests(unittest.TestCase):
    def test_test_case_file_has_all_types(self) -> None:
        cases = exp3.load_test_cases()
        self.assertEqual(len(cases), 28)
        self.assertEqual(
            {case["type"] for case in cases},
            {"直接", "易混", "跨文档", "多跳", "无答案", "越权", "澄清"},
        )

    def test_fact_index_and_evidence_coverage(self) -> None:
        facts = exp3.load_facts()
        fact_index = exp3._build_fact_index(facts)
        trace = {
            "evidence": [
                {"source": "02_注册须知及费用.docx", "section": "费用表"}
            ]
        }
        hits = exp3._evidence_hits(trace, fact_index)
        self.assertIn("02-1", hits)

    def test_citation_exactness_is_checked(self) -> None:
        chunk = Document(
            page_content="学生作者早鸟800元。",
            metadata={
                "chunk_id": "c1",
                "source": "02_注册须知及费用.docx",
                "section": "费用表",
            },
        )
        facts = exp3.load_facts()
        fact_index = exp3._build_fact_index(facts)
        checks = exp3._check_citations(
            {
                "citations": [
                    {
                        "chunk_id": "c1",
                        "source": "02_注册须知及费用.docx",
                        "locator": "费用表",
                        "quote": "早鸟800元",
                    }
                ]
            },
            ["02-1"],
            {"c1": chunk},
            fact_index,
        )
        self.assertTrue(checks[0]["quote_exact"])
        self.assertTrue(checks[0]["matches_required_evidence"])

    def test_metrics_keep_clarification_out_of_refusal_denominator(self) -> None:
        records = [
            {
                "type": "直接",
                "evidence_coverage": True,
                "citation_checks": [
                    {
                        "quote_exact": True,
                        "matches_required_evidence": True,
                    }
                ],
                "judge": {
                    "semantically_correct": True,
                    "citation_supports": True,
                },
                "answer": {"needs_human_review": False},
                "execution_error": None,
            },
            {
                "type": "无答案",
                "judge": {
                    "semantically_correct": True,
                    "refusal_observed": True,
                },
                "answer": {"needs_human_review": True},
                "execution_error": None,
            },
            {
                "type": "澄清",
                "judge": {"semantically_correct": True},
                "answer": {"needs_human_review": False},
                "execution_error": None,
            },
        ]
        metrics = exp3.calculate_metrics(records)
        self.assertEqual(metrics["answerable_count"], 1)
        self.assertEqual(metrics["refusal_count"], 1)
        self.assertEqual(metrics["clarification_count"], 1)
        self.assertEqual(metrics["refusal_accuracy"], 1.0)
        self.assertEqual(metrics["clarification_accuracy"], 1.0)

    def test_judge_json_parser_ignores_explanation(self) -> None:
        parsed = exp3.parse_judge_json(
            '结果：{"semantically_correct":true,"answer":"正确"}。'
        )
        self.assertTrue(parsed["semantically_correct"])


if __name__ == "__main__":
    unittest.main()
