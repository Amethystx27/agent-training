# RAG实验代码框架

## 目录建议

将本目录复制为自己的项目后，建议整理为：

```text
week02-rag/
  data/raw/          # 8份会议DOCX
  data/chunks.jsonl
  index/
  src/rag.py
  results/
  report.md
  requirements.txt
  requirements-lock.txt
  .env.example
  .env               # 本地配置，不提交
```

## 环境

按指导书创建Python 3.11虚拟环境：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
```

若培训教师指定其他Python版本，以教师实际验证过的环境为准。

复制配置模板：

```powershell
Copy-Item .env.example .env
```

填写教师发放的个人模型配置。不要提交`.env`。

## 需要实现

`src/rag.py`提供以下接口骨架：

```python
load_documents(path) -> list[Document]
split_documents(docs) -> list[Document]
build_index(chunks, embedding) -> VectorStore
retrieve(question, k=4) -> list[Document]
answer(question) -> dict
```

建议完成顺序：

1. DOCX/PDF解析与来源元数据。
2. 章节切分和稳定chunk ID。
3. Embedding接口。
4. FAISS构建、保存、重载和重建规则。
5. RAG问答链和引用校验。
6. 无答案、越权和提示注入处理。
7. 28题评价和参数对比。

## 元数据最低要求

每个chunk至少保留：

```text
chunk_id
doc_id
source
section
page或paragraph_range
document_version
file_sha256
```

DOCX不得伪造页码，应使用真实段落范围；PDF使用从1开始的物理页码。

## 解析样例

学生资料中提供了：

- `表格解析样例.docx`：包含2张Word表格；
- `PDF解析样例.pdf`：包含2页可复制文本。

这两个文件只用于验证解析器，不属于正式8份会议知识库，不应默认进入`data/raw/`。

## 答案返回约定

`answer(question)`至少返回：

```python
{
    "answer": str,
    "citations": [
        {
            "chunk_id": str,
            "source": str,
            "locator": str,
            "quote": str,
        }
    ],
    "needs_human_review": bool,
}
```

引用必须来自实际检索结果，`quote`必须能在对应原文中找到。
