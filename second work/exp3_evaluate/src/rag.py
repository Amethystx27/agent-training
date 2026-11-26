"""第二周RAG实验学生代码框架。

本文件只提供接口和约束，所有TODO均由学生实现。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from langchain_core.documents import Document


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_CHUNKS_PATH = PROJECT_ROOT / "data" / "chunks.jsonl"
DEFAULT_INDEX_DIR = PROJECT_ROOT / "index"

CHUNK_SIZE = 600
CHUNK_OVERLAP = 100


def load_documents(path: Path) -> list[Document]:
    """解析DOCX段落/表格及PDF页，并写入来源元数据。"""

    # TODO: 实现文件遍历、DOCX/PDF解析、错误日志和空文本处理。
    raise NotImplementedError


def split_documents(docs: list[Document]) -> list[Document]:
    """按章节和长度切分，生成稳定chunk ID和定位元数据。"""

    # TODO: 建议初始chunk_size=600、overlap=100，并保留来源、章节和定位。
    raise NotImplementedError


class CourseEmbeddings:
    """调用教师提供的OpenAI兼容Embedding接口。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # TODO: 读取EMBEDDING_*配置，批量调用并校验数量和维度。
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        # TODO: 实现单条查询向量化。
        raise NotImplementedError


def build_index(chunks: list[Document], embedding: Any) -> Any:
    """构建并持久化向量索引。"""

    # TODO: 构建FAISS索引，保存manifest并支持可信加载。
    raise NotImplementedError


def retrieve(question: str, k: int = 4) -> list[Document]:
    """从可信本地索引返回带检索分数的证据chunk。"""

    # TODO: 加载索引、执行相似度检索并保留来源元数据。
    raise NotImplementedError


def answer(question: str) -> dict[str, Any]:
    """仅依据检索证据生成结构化答案和可核验引用。"""

    # TODO: 构造有上限的证据上下文并调用教师提供的LLM。
    # TODO: 校验引用来自实际检索结果，且quote可在原文中找到。
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="第二周RAG实验")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("prepare", help="解析文档并生成chunks")
    subparsers.add_parser("index", help="构建向量索引")

    query_parser = subparsers.add_parser("query", help="检索证据")
    query_parser.add_argument("question")
    query_parser.add_argument("--k", type=int, default=4)

    answer_parser = subparsers.add_parser("answer", help="执行RAG问答")
    answer_parser.add_argument("question")

    args = parser.parse_args(argv)
    print(f"TODO: implement command {args.command}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
