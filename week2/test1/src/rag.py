"""实验1：会议文档解析、切分、Embedding与FAISS索引。

实验1只负责离线知识库构建和相似度检索。实验2、3所需的LLM问答、
引用校验和拒答逻辑暂不在本模块中实现。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "data" / "chunks.jsonl"
DEFAULT_INDEX_DIR = PROJECT_ROOT / "index"

CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
SCHEMA_VERSION = "experiment1-v1"
TRUSTED_INDEX_MARKER = "manifest.json"

load_dotenv(PROJECT_ROOT / ".env", override=False)


class ConfigurationError(RuntimeError):
    """实验配置不完整。"""


class DocumentLoadError(RuntimeError):
    """至少一个输入文档无法完成解析。"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_text(text: str) -> str:
    """规范空白，但保留标题、金额、日期和否定条件。"""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        char
        for char in text
        if char in {"\n", "\t"} or not (ord(char) < 32 or ord(char) == 127)
    )
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _doc_id(source: str) -> str:
    match = re.match(r"^(\d+)", source)
    return match.group(1) if match else Path(source).stem


def _clean_heading(text: str) -> str:
    cleaned = re.sub(r"^\d+(?:\.\d+)*[、.．\s]+", "", text.strip())
    return cleaned or text.strip()


def _is_heading(paragraph: Paragraph) -> bool:
    text = paragraph.text.strip()
    if not text:
        return False

    style_name = paragraph.style.name.lower() if paragraph.style is not None else ""
    if style_name.startswith("heading") or style_name == "title":
        return True

    # 教学资料即使丢失样式，也应识别短编号标题。
    return bool(
        len(text) <= 40
        and re.fullmatch(r"\d+(?:\.\d+)*[、.．]\s*[^\d].{0,30}", text)
    )


def _table_to_text(table: Table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells = [_normalise_text(cell.text) for cell in row.cells]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    if len(rows) == 1:
        return " | ".join(value for value in rows[0] if value)

    headers = rows[0]
    lines: list[str] = []
    for row in rows[1:]:
        pairs = [
            f"{headers[index] or f'列{index + 1}'}：{value}"
            for index, value in enumerate(row)
            if value
        ]
        if pairs:
            lines.append("；".join(pairs))
    return "\n".join(lines) if lines else " | ".join(headers)


def _document_version(text: str) -> str:
    match = re.search(r"版本\s*(v\d+(?:\.\d+)*)", text, flags=re.IGNORECASE)
    return match.group(1) if match else "current"


def _parse_docx(path: Path) -> tuple[list[Document], dict[str, Any]]:
    docx = DocxDocument(path)
    source = path.name
    doc_id = _doc_id(source)
    file_hash = _sha256_file(path)

    body = docx.element.body
    paragraph_number = 0
    title = ""
    empty_paragraphs = 0
    table_count = 0
    warnings: list[str] = []
    documents: list[Document] = []

    current_section = "文档说明"
    current_lines: list[str] = []
    section_start: int | None = None
    section_end = 0
    section_tables = 0

    def finish_section() -> None:
        nonlocal current_lines, section_start, section_end, section_tables
        text = _normalise_text("\n".join(current_lines))
        if text:
            start = section_start if section_start is not None else max(1, section_end)
            end = max(start, section_end)
            source_path = (
                path.relative_to(PROJECT_ROOT).as_posix()
                if path.is_relative_to(PROJECT_ROOT)
                else str(path)
            )
            documents.append(
                Document(
                    page_content=text,
                    metadata={
                        "chunk_schema": SCHEMA_VERSION,
                        "doc_id": doc_id,
                        "source": source,
                        "source_path": source_path,
                        "format": "docx",
                        "document_title": title,
                        "section": current_section,
                        "paragraph_range": f"{start}-{end}",
                        "paragraph_start": start,
                        "paragraph_end": end,
                        "locator_type": "paragraph_range",
                        "table_count": section_tables,
                        "document_version": _document_version(text),
                        "file_sha256": file_hash,
                    },
                )
            )
        current_lines = []
        section_start = None
        section_end = 0
        section_tables = 0

    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph_number += 1
            paragraph = Paragraph(child, docx)
            text = _normalise_text(paragraph.text)
            if not text:
                empty_paragraphs += 1
                continue

            if _is_heading(paragraph):
                finish_section()
                current_section = _clean_heading(text)
                current_lines = [text]
                section_start = paragraph_number
                section_end = paragraph_number
                if not title and paragraph.style.name.lower() == "title":
                    title = text
                continue

            if not title and paragraph.style.name.lower() == "title":
                title = text
            if section_start is None:
                section_start = paragraph_number
            current_lines.append(text)
            section_end = paragraph_number

        elif child.tag == qn("w:tbl"):
            table_count += 1
            section_tables += 1
            table_text = _table_to_text(Table(child, docx))
            if table_text:
                if section_start is None:
                    section_start = max(1, paragraph_number)
                current_lines.append(table_text)
                section_end = max(section_end, paragraph_number)
            else:
                warnings.append(f"{source}: empty table at body position {table_count}")

    finish_section()
    if not documents:
        raise ValueError("DOCX contains no extractable text")
    if not title:
        title = documents[0].metadata["section"]

    document_version = _document_version(
        "\n".join(document.page_content for document in documents)
    )
    for document in documents:
        document.metadata["document_title"] = title
        document.metadata["document_version"] = document_version

    stats = {
        "source": source,
        "sections": len(documents),
        "paragraphs": paragraph_number,
        "empty_paragraphs": empty_paragraphs,
        "tables": table_count,
        "chars": sum(len(document.page_content) for document in documents),
        "warnings": warnings,
        "file_sha256": file_hash,
    }
    return documents, stats


def _parse_pdf(path: Path) -> tuple[list[Document], dict[str, Any]]:
    source = path.name
    doc_id = _doc_id(source)
    file_hash = _sha256_file(path)
    reader = PdfReader(path)
    documents: list[Document] = []
    warnings: list[str] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = _normalise_text(page.extract_text() or "")
        if not text:
            warnings.append(
                f"{source}: page {page_number} has no extractable text; OCR may be required"
            )
            continue
        source_path = (
            path.relative_to(PROJECT_ROOT).as_posix()
            if path.is_relative_to(PROJECT_ROOT)
            else str(path)
        )
        documents.append(
            Document(
                page_content=text,
                metadata={
                    "chunk_schema": SCHEMA_VERSION,
                    "doc_id": doc_id,
                    "source": source,
                    "source_path": source_path,
                    "format": "pdf",
                    "document_title": path.stem,
                    "section": f"第{page_number}页",
                    "page": page_number,
                    "locator_type": "page",
                    "document_version": _document_version(text),
                    "file_sha256": file_hash,
                },
            )
        )

    if not documents:
        raise ValueError("PDF contains no extractable text; OCR may be required")

    document_version = _document_version(
        "\n".join(document.page_content for document in documents)
    )
    for document in documents:
        document.metadata["document_version"] = document_version

    stats = {
        "source": source,
        "sections": len(documents),
        "pages": len(reader.pages),
        "empty_pages": len(warnings),
        "chars": sum(len(document.page_content) for document in documents),
        "warnings": warnings,
        "file_sha256": file_hash,
    }
    return documents, stats


def _input_files(path: Path) -> list[Path]:
    if not path.exists():
        raise FileNotFoundError(f"input path does not exist: {path}")
    if path.is_file():
        candidates = [path]
    else:
        candidates = sorted(
            item
            for item in path.rglob("*")
            if item.is_file() and item.suffix.lower() in {".docx", ".pdf"}
        )
    candidates = [item for item in candidates if not item.name.startswith("~$")]
    if not candidates:
        raise ValueError(f"no DOCX or PDF files found under: {path}")
    return candidates


def _write_parse_reports(
    results_dir: Path,
    stats: dict[str, Any],
    warnings: list[str],
    errors: list[str],
) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "parse_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log_lines = [f"[ERROR] {error}" for error in errors]
    log_lines.extend(f"[WARNING] {warning}" for warning in warnings)
    if log_lines:
        log_text = "\n".join(log_lines) + "\n"
    else:
        log_text = "No parser errors or warnings.\n"
    (results_dir / "parse_errors.log").write_text(log_text, encoding="utf-8")


def load_corpus(
    path: Path,
    report_dir: Path | None = DEFAULT_RESULTS_DIR,
) -> tuple[list[Document], dict[str, Any]]:
    """解析所有输入文件，并返回文档级统计。

    任一文件解析失败都会抛出 DocumentLoadError，防止静默遗漏资料。
    空PDF页或空表格会写入警告日志，但不会伪造成有效正文。
    """

    files = _input_files(path)
    documents: list[Document] = []
    file_stats: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    for file_path in files:
        try:
            if file_path.suffix.lower() == ".docx":
                parsed, stat = _parse_docx(file_path)
            elif file_path.suffix.lower() == ".pdf":
                parsed, stat = _parse_pdf(file_path)
            else:
                raise ValueError(f"unsupported file type: {file_path.suffix}")
            documents.extend(parsed)
            file_stats.append(stat)
            warnings.extend(stat.get("warnings", []))
        except Exception as exc:  # 报告所有文件级错误，不让单个文件静默消失
            errors.append(f"{file_path.name}: {type(exc).__name__}: {exc}")

    by_extension: dict[str, int] = {}
    for file_path in files:
        extension = file_path.suffix.lower()
        by_extension[extension] = by_extension.get(extension, 0) + 1

    stats = {
        "schema_version": SCHEMA_VERSION,
        "input_path": str(path.resolve()),
        "generated_at": _utc_now(),
        "file_count": len(files),
        "file_types": by_extension,
        "document_count": len(documents),
        "empty_text_count": sum(
            1 for stat in file_stats if stat.get("chars", 0) == 0
        )
        + len(errors),
        "files": file_stats,
        "errors": errors,
        "warnings": warnings,
    }

    if report_dir is not None:
        _write_parse_reports(report_dir, stats, warnings, errors)
    if errors:
        raise DocumentLoadError(
            "one or more files could not be parsed:\n" + "\n".join(errors)
        )
    return documents, stats


def load_documents(path: Path) -> list[Document]:
    """实验接口：读取DOCX段落/表格和PDF页。"""

    documents, _ = load_corpus(Path(path))
    return documents


def _stable_chunk_id(
    source: str,
    file_hash: str,
    section: str,
    locator: str,
    chunk_index: int,
    text: str,
) -> str:
    identity = "\x1f".join(
        [
            source,
            file_hash,
            section,
            locator,
            str(chunk_index),
            text,
        ]
    )
    return _sha256_bytes(identity.encode("utf-8"))


def split_documents(docs: list[Document]) -> list[Document]:
    """按章节边界、段落和中文标点切分，并生成稳定chunk_id。"""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        keep_separator="end",
        add_start_index=True,
    )
    chunks: list[Document] = []
    counters: dict[str, int] = {}

    for source_document in sorted(
        docs,
        key=lambda item: (
            item.metadata.get("source", ""),
            int(item.metadata.get("paragraph_start", item.metadata.get("page", 0)) or 0),
            item.metadata.get("section", ""),
        ),
    ):
        pieces = splitter.create_documents(
            [source_document.page_content],
            metadatas=[dict(source_document.metadata)],
        )
        for piece in pieces:
            content = _normalise_text(piece.page_content)
            if not content:
                continue
            metadata = dict(piece.metadata)
            source = str(metadata["source"])
            chunk_index = counters.get(source, 0)
            counters[source] = chunk_index + 1
            locator = str(
                metadata.get("paragraph_range")
                or metadata.get("page")
                or metadata.get("section", "")
            )
            metadata["chunk_index"] = chunk_index
            metadata["chunk_id"] = _stable_chunk_id(
                source=source,
                file_hash=str(metadata.get("file_sha256", "")),
                section=str(metadata.get("section", "")),
                locator=locator,
                chunk_index=chunk_index,
                text=content,
            )
            metadata["char_count"] = len(content)
            metadata["chunk_size"] = CHUNK_SIZE
            metadata["chunk_overlap"] = CHUNK_OVERLAP
            metadata["char_start"] = int(metadata.get("start_index", 0))
            metadata["char_end"] = metadata["char_start"] + len(content)
            chunks.append(Document(page_content=content, metadata=metadata))

    chunk_ids = [chunk.metadata["chunk_id"] for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("duplicate chunk_id detected")
    return chunks


def save_chunks(chunks: list[Document], path: Path = DEFAULT_CHUNKS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            record = {
                "page_content": chunk.page_content,
                "metadata": chunk.metadata,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_chunks(path: Path = DEFAULT_CHUNKS_PATH) -> list[Document]:
    chunks: list[Document] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                chunks.append(
                    Document(
                        page_content=record["page_content"],
                        metadata=record["metadata"],
                    )
                )
            except Exception as exc:
                raise ValueError(
                    f"invalid chunk record at {path}:{line_number}: {exc}"
                ) from exc
    if not chunks:
        raise ValueError(f"no chunks found in: {path}")
    return chunks


class CourseEmbeddings(Embeddings):
    """OpenAI兼容Embedding接口，缺少模型配置时拒绝发起调用。"""

    def __init__(self) -> None:
        self.api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("EMBEDDING_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        self.model = os.getenv("EMBEDDING_MODEL")
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))
        self.timeout = float(os.getenv("EMBEDDING_TIMEOUT", "60"))
        self._dimension: int | None = None

        if not self.api_key:
            raise ConfigurationError(
                "EMBEDDING_API_KEY is missing (OPENAI_API_KEY fallback is also empty)"
            )
        if not self.model:
            raise ConfigurationError("EMBEDDING_MODEL is missing")
        if self.batch_size <= 0:
            raise ConfigurationError("EMBEDDING_BATCH_SIZE must be positive")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url or None,
            timeout=self.timeout,
            max_retries=2,
        )

    @property
    def dimension(self) -> int | None:
        return self._dimension

    @property
    def model_identifier(self) -> str:
        return self.model

    def _validate_vector(
        self,
        vector: Iterable[float],
        reference: int | None = None,
    ) -> list[float]:
        values = [float(value) for value in vector]
        if not values:
            raise ValueError("Embedding API returned an empty vector")
        if reference is None:
            reference = len(values)
        if len(values) != reference:
            raise ValueError(
                f"Embedding dimension mismatch: expected {reference}, got {len(values)}"
            )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Embedding API returned a non-finite value")
        return values

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = self.client.embeddings.create(model=self.model, input=batch)
            ordered = sorted(response.data, key=lambda item: item.index)
            if len(ordered) != len(batch):
                raise ValueError(
                    f"Embedding count mismatch: sent {len(batch)}, received {len(ordered)}"
                )
            if [item.index for item in ordered] != list(range(len(batch))):
                raise ValueError("Embedding API returned non-contiguous indices")
            for item in ordered:
                vector = self._validate_vector(item.embedding, self._dimension)
                if self._dimension is None:
                    self._dimension = len(vector)
                vectors.append(vector)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        response = self.client.embeddings.create(model=self.model, input=[text])
        if len(response.data) != 1:
            raise ValueError("Embedding query API did not return exactly one vector")
        return self._validate_vector(response.data[0].embedding, self._dimension)


def _validate_chunks(chunks: list[Document]) -> None:
    required = {
        "chunk_id",
        "doc_id",
        "source",
        "section",
        "document_version",
        "file_sha256",
    }
    seen: set[str] = set()
    for index, chunk in enumerate(chunks):
        if not chunk.page_content.strip():
            raise ValueError(f"chunk {index} is empty")
        missing = required - set(chunk.metadata)
        if missing:
            raise ValueError(f"chunk {index} missing metadata: {sorted(missing)}")
        if "page" not in chunk.metadata and "paragraph_range" not in chunk.metadata:
            raise ValueError(f"chunk {index} has no page or paragraph locator")
        chunk_id = str(chunk.metadata["chunk_id"])
        if chunk_id in seen:
            raise ValueError(f"duplicate chunk_id: {chunk_id}")
        seen.add(chunk_id)


def build_index(
    chunks: list[Document],
    embedding: Embeddings,
    index_dir: Path = DEFAULT_INDEX_DIR,
) -> Any:
    """构建FAISS索引并写入可校验清单。"""

    from langchain_community.vectorstores import FAISS

    _validate_chunks(chunks)
    index_dir = Path(index_dir)
    index_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = index_dir.with_name(index_dir.name + ".building")
    backup_dir = index_dir.with_name(index_dir.name + ".backup")
    if temporary_dir.exists():
        shutil.rmtree(temporary_dir)
    temporary_dir.mkdir(parents=True)

    try:
        store = FAISS.from_documents(chunks, embedding)
        store.save_local(str(temporary_dir))
        files = {
            str(chunk.metadata["source"]): str(chunk.metadata["file_sha256"])
            for chunk in chunks
        }
        source_paths = {
            str(chunk.metadata["source"]): str(chunk.metadata["source_path"])
            for chunk in chunks
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _utc_now(),
            "chunk_count": len(chunks),
            "source_file_count": len(files),
            "files": dict(sorted(files.items())),
            "source_paths": dict(sorted(source_paths.items())),
            "embedding_model": getattr(
                embedding,
                "model_identifier",
                type(embedding).__name__,
            ),
            "embedding_dimension": int(store.index.d),
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "distance_strategy": str(
                getattr(store, "distance_strategy", "unknown")
            ),
            "trusted_local_index": True,
        }
        (temporary_dir / TRUSTED_INDEX_MARKER).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        if index_dir.exists():
            index_dir.rename(backup_dir)
        temporary_dir.rename(index_dir)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        return store
    except Exception:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir)
        if backup_dir.exists() and not index_dir.exists():
            backup_dir.rename(index_dir)
        raise


def _load_index(index_dir: Path, embedding: Embeddings) -> Any:
    from langchain_community.vectorstores import FAISS

    manifest_path = Path(index_dir) / TRUSTED_INDEX_MARKER
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"trusted index manifest not found: {manifest_path}; build the index first"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("trusted_local_index") is not True:
        raise ValueError("refusing to load an index not marked as trusted local output")
    expected_model = manifest.get("embedding_model")
    actual_model = getattr(embedding, "model_identifier", type(embedding).__name__)
    if expected_model != actual_model:
        raise ConfigurationError(
            "Embedding model changed: "
            f"index={expected_model!r}, current={actual_model!r}; rebuild required"
        )

    source_hashes = manifest.get("files", {})
    source_paths = manifest.get("source_paths", {})
    for source, expected_hash in source_hashes.items():
        path_text = source_paths.get(source)
        if not path_text:
            continue
        source_path = Path(path_text)
        if not source_path.is_absolute():
            source_path = PROJECT_ROOT / source_path
        if not source_path.exists():
            raise ConfigurationError(
                f"source file is missing: {source}; rebuild required"
            )
        actual_hash = _sha256_file(source_path)
        if actual_hash != expected_hash:
            raise ConfigurationError(
                f"source file changed: {source}; rebuild required"
            )

    # 只加载本程序生成且带清单的本地索引，绝不加载上传或第三方索引。
    store = FAISS.load_local(
        str(index_dir),
        embedding,
        allow_dangerous_deserialization=True,
    )
    expected_dimension = int(manifest["embedding_dimension"])
    if int(store.index.d) != expected_dimension:
        raise ValueError("FAISS index dimension does not match its manifest")
    return store


def retrieve(
    question: str,
    k: int = 4,
    index_dir: Path = DEFAULT_INDEX_DIR,
    embedding: Embeddings | None = None,
) -> list[Document]:
    """加载可信索引并返回实际证据，不调用LLM。"""

    if not question.strip():
        raise ValueError("question must not be empty")
    if k <= 0:
        raise ValueError("k must be positive")
    embedding = embedding or CourseEmbeddings()
    store = _load_index(Path(index_dir), embedding)
    results = store.similarity_search_with_score(question, k=k)
    documents: list[Document] = []
    for document, score in results:
        metadata = dict(document.metadata)
        metadata["retrieval_score"] = float(score)
        documents.append(Document(page_content=document.page_content, metadata=metadata))
    return documents


def answer(question: str) -> dict:
    """实验2公共接口；实现位于本目录的rag_qa模块。"""

    from src.rag_qa import answer as rag_answer

    return rag_answer(question)


def prepare(
    raw_dir: Path = DEFAULT_RAW_DIR,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    chunks_path: Path = DEFAULT_CHUNKS_PATH,
) -> tuple[list[Document], dict[str, Any]]:
    documents, stats = load_corpus(Path(raw_dir), Path(results_dir))
    chunks = split_documents(documents)
    save_chunks(chunks, Path(chunks_path))

    chunk_stats = {
        "chunk_count": len(chunks),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "min_chars": min(len(chunk.page_content) for chunk in chunks),
        "max_chars": max(len(chunk.page_content) for chunk in chunks),
        "avg_chars": round(
            sum(len(chunk.page_content) for chunk in chunks) / len(chunks), 2
        ),
        "unique_chunk_ids": len({chunk.metadata["chunk_id"] for chunk in chunks}),
    }
    stats["chunks"] = chunk_stats
    stats["chunks_path"] = str(Path(chunks_path).resolve())
    Path(results_dir).mkdir(parents=True, exist_ok=True)
    (Path(results_dir) / "parse_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return chunks, stats


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    _configure_logging()
    parser = argparse.ArgumentParser(description="实验1：RAG离线知识库")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="解析、切分并生成chunks.jsonl",
    )
    prepare_parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    prepare_parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    prepare_parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)

    index_parser = subparsers.add_parser(
        "index",
        help="调用Embedding并构建FAISS索引",
    )
    index_parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    index_parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)

    query_parser = subparsers.add_parser("query", help="加载索引并检索")
    query_parser.add_argument("question")
    query_parser.add_argument("--k", type=int, default=4)
    query_parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)

    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            chunks, stats = prepare(args.raw_dir, args.results_dir, args.chunks_path)
            print(json.dumps(stats["chunks"], ensure_ascii=False, indent=2))
            print(f"写入 {len(chunks)} 个chunks: {args.chunks_path.resolve()}")
        elif args.command == "index":
            chunks = load_chunks(args.chunks_path)
            build_index(chunks, CourseEmbeddings(), args.index_dir)
            print(f"索引已写入: {args.index_dir.resolve()}")
        elif args.command == "query":
            results = retrieve(args.question, args.k, args.index_dir)
            for item in results:
                print(
                    json.dumps(
                        {
                            "score": item.metadata.get("retrieval_score"),
                            "source": item.metadata.get("source"),
                            "section": item.metadata.get("section"),
                            "paragraph_range": item.metadata.get("paragraph_range"),
                            "page": item.metadata.get("page"),
                            "chunk_id": item.metadata.get("chunk_id"),
                            "text": item.page_content,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
        return 0
    except (ConfigurationError, DocumentLoadError, FileNotFoundError, ValueError) as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
