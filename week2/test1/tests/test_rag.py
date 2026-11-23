from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document as DocxDocument
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src import rag  # noqa: E402


class DeterministicEmbeddings(Embeddings):
    model_identifier = "deterministic-test-embedding"

    @staticmethod
    def _vector(text: str, dimension: int = 16) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [float(digest[index] + 1) for index in range(dimension)]
        length = math.sqrt(sum(value * value for value in values))
        return [value / length for value in values]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class RagExperimentOneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _create_docx(self, name: str = "01_测试通知.docx") -> Path:
        path = self.root / name
        document = DocxDocument()
        document.add_heading("测试通知", level=0)
        document.add_paragraph("本资料为虚构教学资料。")
        document.add_heading("1. 费用表", level=2)
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "身份"
        table.cell(0, 1).text = "价格"
        table.cell(1, 0).text = "学生作者"
        table.cell(1, 1).text = "800元"
        document.add_heading("2. 日期", level=2)
        document.add_paragraph(
            "摘要截止2027年3月10日18:00；全文截止2027年3月27日18:00。"
        )
        document.save(path)
        return path

    def test_docx_parser_preserves_sections_and_tables(self) -> None:
        path = self._create_docx()
        documents, stats = rag.load_corpus(path, report_dir=None)

        self.assertEqual(stats["file_count"], 1)
        self.assertEqual(stats["files"][0]["tables"], 1)
        self.assertEqual(len(documents), 3)
        self.assertEqual(
            [document.metadata["section"] for document in documents],
            ["测试通知", "费用表", "日期"],
        )
        fee_document = next(
            document
            for document in documents
            if document.metadata["section"] == "费用表"
        )
        self.assertIn("身份：学生作者", fee_document.page_content)
        self.assertIn("价格：800元", fee_document.page_content)
        self.assertNotIn("page", fee_document.metadata)
        self.assertIn("paragraph_range", fee_document.metadata)

    def test_chunk_ids_are_stable_and_metadata_is_complete(self) -> None:
        path = self._create_docx()
        documents, _ = rag.load_corpus(path, report_dir=None)

        first = rag.split_documents(documents)
        second = rag.split_documents(documents)

        self.assertEqual(len(first), len(second))
        self.assertEqual(
            [chunk.metadata["chunk_id"] for chunk in first],
            [chunk.metadata["chunk_id"] for chunk in second],
        )
        self.assertEqual(
            len(first),
            len({chunk.metadata["chunk_id"] for chunk in first}),
        )
        for chunk in first:
            for field in (
                "chunk_id",
                "doc_id",
                "source",
                "section",
                "paragraph_range",
                "document_version",
                "file_sha256",
            ):
                self.assertIn(field, chunk.metadata)

    def test_document_version_applies_to_every_section(self) -> None:
        path = self.root / "08_更正通知.docx"
        document = DocxDocument()
        document.add_heading("更正通知", level=0)
        document.add_heading("1. 发布", level=2)
        document.add_paragraph("2027年3月15日发布，版本v2。")
        document.add_heading("2. 会场", level=2)
        document.add_paragraph("智能会务分会改为A203。")
        document.save(path)

        documents, _ = rag.load_corpus(path, report_dir=None)

        self.assertGreater(len(documents), 1)
        self.assertTrue(
            all(
                document.metadata["document_version"] == "v2"
                for document in documents
            )
        )

    def test_chunks_round_trip_through_jsonl(self) -> None:
        path = self._create_docx()
        documents, _ = rag.load_corpus(path, report_dir=None)
        chunks = rag.split_documents(documents)
        chunks_path = self.root / "chunks.jsonl"

        rag.save_chunks(chunks, chunks_path)
        loaded = rag.load_chunks(chunks_path)

        self.assertEqual(
            [(chunk.page_content, chunk.metadata) for chunk in chunks],
            [(chunk.page_content, chunk.metadata) for chunk in loaded],
        )

    def test_faiss_index_persists_and_reloads(self) -> None:
        path = self._create_docx()
        documents, _ = rag.load_corpus(path, report_dir=None)
        chunks = rag.split_documents(documents)
        embedding = DeterministicEmbeddings()
        index_dir = self.root / "index"

        rag.build_index(chunks, embedding, index_dir)
        rag.build_index(chunks, embedding, index_dir)
        results = rag.retrieve(
            "学生作者价格",
            k=2,
            index_dir=index_dir,
            embedding=embedding,
        )

        manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["chunk_count"], len(chunks))
        self.assertEqual(manifest["embedding_dimension"], 16)
        self.assertEqual(manifest["embedding_model"], embedding.model_identifier)
        self.assertGreater(len(results), 0)
        self.assertIn("retrieval_score", results[0].metadata)

    def test_empty_docx_is_reported_as_failure(self) -> None:
        path = self.root / "01_空文档.docx"
        DocxDocument().save(path)

        with self.assertRaises(rag.DocumentLoadError):
            rag.load_corpus(path, report_dir=self.root / "results")
        self.assertTrue(
            (self.root / "results" / "parse_errors.log")
            .read_text(encoding="utf-8")
            .startswith("[ERROR]")
        )

    def test_modified_source_invalidates_index(self) -> None:
        path = self._create_docx()
        documents, _ = rag.load_corpus(path, report_dir=None)
        chunks = rag.split_documents(documents)
        embedding = DeterministicEmbeddings()
        index_dir = self.root / "index"
        rag.build_index(chunks, embedding, index_dir)

        with path.open("ab") as handle:
            handle.write(b"\x00")

        with self.assertRaises(rag.ConfigurationError):
            rag.retrieve(
                "学生作者价格",
                index_dir=index_dir,
                embedding=embedding,
            )


if __name__ == "__main__":
    unittest.main()
