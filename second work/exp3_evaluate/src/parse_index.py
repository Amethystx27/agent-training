"""解析 DOCX/PDF 并构建 FAISS 索引。"""
import json, os, re
from pathlib import Path
import faiss
import numpy as np
from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from .common import *

CHUNK_SIZE = 600
CHUNK_OVERLAP = 100

def _docx_sections(path: Path) -> list[tuple[str, str, str]]:
    doc = DocxDocument(str(path))
    current_section, blocks, para_idx, para_start = "前言", [], 0, 0
    sections = []

    def flush(end_idx: int):
        nonlocal blocks
        text = "\n".join(blocks).strip()
        if text: sections.append((current_section, text, f"{para_start}-{max(end_idx, para_start)}"))
        blocks = []

    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            p = Paragraph(child, doc)
            text = (p.text or "").strip()
            style = p.style.name if p.style else ""
            para_idx += 1
            is_heading = style.startswith("Heading") or "标题" in style or re.match(r"^\d+(\.\d+)*[、.\s]+", text)
            if is_heading:
                if blocks: flush(para_idx - 1)
                current_section, para_start, blocks = text, para_idx, [text]
            elif text:
                blocks.append(text)
        elif child.tag == qn("w:tbl"):
            table = Table(child, doc)
            rows = [" | ".join([(c.text or "").strip().replace("\n", " ") for c in row.cells]) for row in table.rows]
            if rows: blocks.append("[表格]\n" + "\n".join(rows))
    flush(para_idx)
    if not sections:
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        if paras: sections.append(("全文", "\n".join(paras), f"1-{len(paras)}"))
    return sections

def load_documents(path: Path):
    files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in {".docx", ".pdf"})
    stats = {"files": 0, "docx": 0, "pdf": 0, "empty": 0, "errors": []}
    docs = []
    for f in files:
        stats["files"] += 1
        f_hash = sha256_file(f)
        try:
            if f.suffix.lower() == ".docx":
                stats["docx"] += 1
                for sec, text, prange in _docx_sections(f):
                    if not text.strip(): stats["empty"] += 1; continue
                    docs.append(Document(page_content=text, metadata={
                        "source": f.name, "doc_id": f.stem, "section": sec,
                        "paragraph_range": prange, "locator": f"paragraph_range={prange}",
                        "locator_type": "paragraph_range", "document_version": "v1", "file_sha256": f_hash
                    }))
            else:
                stats["pdf"] += 1
                reader = PdfReader(str(f))
                for pno, page in enumerate(reader.pages, start=1):
                    text = (page.extract_text() or "").strip()
                    if not text: stats["empty"] += 1; continue
                    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), f"第{pno}页")
                    docs.append(Document(page_content=text, metadata={
                        "source": f.name, "doc_id": f.stem, "section": first_line[:80],
                        "page": pno, "locator": f"page={pno}",
                        "locator_type": "page", "document_version": "v1", "file_sha256": f_hash
                    }))
        except Exception as e:
            stats["errors"].append(str(e))
    return docs, stats

def split_documents(docs: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=int(os.getenv("CHUNK_SIZE", str(CHUNK_SIZE))),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", str(CHUNK_OVERLAP))),
        separators=["\n\n", "\n", "。", "；", "，", " "], keep_separator=True
    )
    chunks = []
    for doc in docs:
        for i, piece in enumerate(splitter.split_text(doc.page_content)):
            if not piece.strip(): continue
            meta = dict(doc.metadata)
            meta["chunk_index"] = i
            raw_id = f"{meta.get('doc_id')}|{meta.get('locator')}|{meta.get('section')}|{i}|{sha256_text(piece)[:16]}"
            meta["chunk_id"] = sha256_text(raw_id)[:16]
            chunks.append(Document(page_content=piece.strip(), metadata=meta))
    return chunks

def build_index(chunks: list[Document], embedding: CourseEmbeddings):
    ensure_dirs()
    vecs = embedding.embed_documents([c.page_content for c in chunks])
    arr = np.asarray(vecs, dtype=np.float32)
    faiss.normalize_L2(arr)
    index = faiss.IndexFlatIP(arr.shape[1])
    index.add(arr)
    faiss.write_index(index, str(DEFAULT_INDEX_DIR / "index.faiss"))
    write_jsonl(DEFAULT_INDEX_DIR / "metadata.jsonl", [{"text": c.page_content, "metadata": c.metadata} for c in chunks])
    manifest = {
        "embedding_model": embedding.model, "dimension": int(arr.shape[1]),
        "chunk_count": len(chunks), "chunk_size": int(os.getenv("CHUNK_SIZE", "600"))
    }
    (DEFAULT_INDEX_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))

def main():
    ensure_dirs()
    docs, stats = load_documents(DEFAULT_RAW_DIR)
    chunks = split_documents(docs)
    write_jsonl(DEFAULT_CHUNKS_PATH, [{"chunk_id": c.metadata["chunk_id"], "text": c.page_content, "metadata": c.metadata} for c in chunks])
    stats["chunk_count"] = len(chunks)
    DEFAULT_PARSE_STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"解析完成，共 {len(chunks)} 个 chunks。")
    build_index(chunks, CourseEmbeddings())
    print("索引构建完成。")

if __name__ == "__main__":
    main()