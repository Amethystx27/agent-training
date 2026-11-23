from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import rag, rag_qa  # noqa: E402


def make_document(
    chunk_id: str,
    source: str,
    section: str,
    text: str,
) -> Document:
    return Document(
        page_content=text,
        metadata={
            "chunk_id": chunk_id,
            "source": source,
            "section": section,
            "paragraph_range": "1-2",
            "document_version": "current",
            "retrieval_score": 0.1,
        },
    )


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    def create(self, **kwargs: object) -> object:
        self.calls += 1
        message = SimpleNamespace(content=self.content, reasoning_content="")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=message,
                    finish_reason="stop",
                )
            ],
            model="fake-model",
            usage=None,
        )


class FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


class RagExperimentTwoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = make_document(
            "chunk-02",
            "02_注册须知及费用.docx",
            "费用表",
            "学生作者早鸟800元、常规1000元；早鸟以5月1日23:59前到账为准。",
        )
        self.room = make_document(
            "chunk-03",
            "03_住宿交通.docx",
            "住宿",
            "标间每间每晚300元，可住2人；入住至退房计3晚。",
        )
        self.calls: list[str] = []

    def retriever(self, question: str, k: int) -> list[Document]:
        self.calls.append(question)
        if question.startswith("会议住宿") or question.startswith("住宿费用"):
            return [self.room]
        return [self.rules]

    def test_cross_document_question_is_split_and_citations_are_validated(self) -> None:
        content = json.dumps(
            {
                "answer": "注册1600元，住宿900元，共2500元CNY[S1][S2]。",
                "citations": [
                    {
                        "evidence_id": "S1",
                        "quote": "学生作者早鸟800元、常规1000元",
                    },
                    {
                        "evidence_id": "S2",
                        "quote": "标间每间每晚300元，可住2人；入住至退房计3晚。",
                    },
                ],
                "needs_human_review": False,
            },
            ensure_ascii=False,
        )
        engine = rag_qa.RAGEngine(
            retriever=self.retriever,
            llm_client=FakeClient(content),
        )

        trace = engine.answer_with_trace(
            "两名学生作者早鸟各注册且合住标间三晚，共多少？"
        )

        self.assertGreaterEqual(len(self.calls), 3)
        self.assertEqual(len(trace["result"]["citations"]), 2)
        self.assertEqual(
            trace["result"]["citations"][0]["chunk_id"],
            "chunk-02",
        )
        self.assertFalse(trace["result"]["needs_human_review"])
        for citation in trace["result"]["citations"]:
            source = self.rules if citation["source"].startswith("02") else self.room
            self.assertIn(citation["quote"], source.page_content)

    def test_unknown_evidence_reference_is_rejected(self) -> None:
        content = json.dumps(
            {
                "answer": "答案见[S9]。",
                "citations": [
                    {"evidence_id": "S9", "quote": "不存在的证据"}
                ],
                "needs_human_review": False,
            },
            ensure_ascii=False,
        )
        engine = rag_qa.RAGEngine(
            retriever=self.retriever,
            llm_client=FakeClient(content),
        )

        trace = engine.answer_with_trace("学生作者价格？")

        self.assertEqual(trace["result"]["citations"], [])
        self.assertTrue(trace["result"]["needs_human_review"])
        self.assertTrue(trace["validation_warnings"])

    def test_empty_retrieval_returns_review_without_calling_llm(self) -> None:
        client = FakeClient("{}")
        engine = rag_qa.RAGEngine(
            retriever=lambda question, k: [],
            llm_client=client,
        )

        trace = engine.answer_with_trace("知识库没有的问题")

        self.assertEqual(client.chat.completions.calls, 0)
        self.assertTrue(trace["result"]["needs_human_review"])
        self.assertIn("资料未提供", trace["result"]["answer"])

    def test_model_json_can_be_wrapped_in_explanation(self) -> None:
        parsed = rag_qa.parse_model_json(
            '结果如下：{"answer":"ok","citations":[]} 以上是结果。'
        )
        self.assertEqual(parsed["answer"], "ok")

    def test_exact_quote_recovers_original_whitespace(self) -> None:
        source = "第一行\n第二行 价格800元"
        quote = rag_qa.extract_exact_quote(source, "第一行 第二行价格800元")
        self.assertEqual(quote, source)

    def test_subqueries_cover_registration_and_lodging(self) -> None:
        queries = rag_qa.derive_subqueries(
            "两名学生作者注册并合住标间三晚一共多少钱？"
        )
        self.assertGreaterEqual(len(queries), 3)
        self.assertTrue(any("注册费" in query for query in queries))
        self.assertTrue(any("住宿" in query for query in queries))

    def test_subqueries_make_vague_cfp_and_payment_questions_explicit(self) -> None:
        cfp_queries = rag_qa.derive_subqueries("征稿主题有哪些？")
        payment_queries = rag_qa.derive_subqueries(
            "4月30日传凭证，5月2日到账，交多少？"
        )
        self.assertTrue(any("会议概况" in query for query in cfp_queries))
        self.assertTrue(any("实际到账时间" in query for query in payment_queries))

    def test_experiment_one_answer_wrapper_delegates_to_experiment_two(self) -> None:
        expected = {
            "answer": "ok",
            "citations": [],
            "needs_human_review": False,
        }
        with patch("src.rag_qa.answer", return_value=expected) as delegated:
            result = rag.answer("测试问题")

        delegated.assert_called_once_with("测试问题")
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
