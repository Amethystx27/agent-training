"""公共模块：路径、哈希、Embedding 与 LLM 客户端。"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "data" / "chunks.jsonl"
DEFAULT_INDEX_DIR = PROJECT_ROOT / "index"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_PARSE_STATS = PROJECT_ROOT / "data" / "parse_stats.json"
DEFAULT_ERROR_LOG = PROJECT_ROOT / "data" / "parse_errors.log"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", "", text or "")

def ensure_dirs() -> None:
    for d in (PROJECT_ROOT / "data", DEFAULT_RAW_DIR, DEFAULT_INDEX_DIR, DEFAULT_RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

class CourseEmbeddings:
    def __init__(self) -> None:
        self.api_key = os.getenv("EMBEDDING_API_KEY", "").strip()
        self.base_url = os.getenv("EMBEDDING_BASE_URL", "").strip()
        self.model = os.getenv("EMBEDDING_MODEL", "").strip()
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))
        if not self.api_key or not self.model:
            raise RuntimeError("缺少 EMBEDDING_API_KEY 或 EMBEDDING_MODEL")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url or None)
        self.dimension: int | None = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts: return []
        vectors = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            resp = self.client.embeddings.create(model=self.model, input=batch)
            data = sorted(resp.data, key=lambda x: x.index)
            vecs = [item.embedding for item in data]
            for v in vecs:
                if self.dimension is None: self.dimension = len(v)
                elif len(v) != self.dimension: raise RuntimeError("维度不一致")
            vectors.extend(vecs)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists(): return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip(): rows.append(json.loads(line))
    return rows