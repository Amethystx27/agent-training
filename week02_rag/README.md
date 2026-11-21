# 第二周 RAG 企业知识库开发

会议知识库问答系统。语料为 8 份教学虚构会议 DOCX，支持解析入库、检索增强问答、来源展示与无依据拒答。

## 目录结构

```
week02_rag/
  data/raw/            # 8份会议DOCX（唯一正式语料）
  data/samples/        # 解析样例（仅验证解析器，不入库）
  data/chunks.jsonl    # 切分结果（prepare 生成）
  data/测试问题.md      # 28题
  index/               # FAISS索引+manifest（不入Git，可从原资料重建）
  src/rag.py           # 核心实现：解析/切分/Embedding/索引/检索/问答
  results/             # 解析日志、28题原始输出、逐题评价
  run_experiments.py   # 实验3评估与参数对比
  requirements.txt
  requirements-lock.txt
  .env.example         # 配置模板（可提交）
  .env                 # 本地真实密钥（禁止提交）
```

## 环境

Python 3.11（本地实测 3.11.16）：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip check
Copy-Item .env.example .env   # 然后填入教师发放的 LLM_* / EMBEDDING_* 配置
```

说明：锁文件原为 Python 3.12 冻结（numpy 2.5.5 需 3.12+）；本地 3.11 环境改用兼容的 numpy 2.4.6，其余按锁文件版本安装。Embedding 接口实测维度 1024。

## 运行

```powershell
# 实验1：解析 + 切分 -> data/chunks.jsonl
python src/rag.py samplecheck          # 先验证解析器对样例表格/PDF的处理
python src/rag.py prepare
python src/rag.py index                # 构建FAISS索引+manifest

# 实验2：检索与问答（CLI）
python src/rag.py query "学生作者早鸟注册多少钱？" --k 4
python src/rag.py query "征稿主题有哪些？" --k 4 --mode vector   # 纯向量基线（对比用）
python src/rag.py answer "两名学生作者早鸟注册且合住标间三晚共多少？"

# 实验3：28题评估 + 参数对比
python run_experiments.py --k 4 --tag k4
python run_experiments.py --k 6 --tag k6
```

重建索引：文件改动或 Embedding 模型更换后必须重新执行 `prepare` + `index`。`index/` 不纳入 Git，但可从 `data/raw/` 完全重建。加载时会校验 manifest 中记录的源文件 SHA256，哈希不匹配则拒绝加载并提示重建，避免加载来源不明的索引。

## 检索模式
默认 `hybrid`：向量检索（余弦）+ BM25 关键词检索，两榜分数各自 min-max 归一化后按 0.5/0.5 加权融合。BM25 中文按单字+二字词切分，无需外部分词依赖。这样可缓解“征稿主题有哪些？”这类短/抽象查询因纯语义相似度不足而漏召回的问题（主题句所在块在纯向量 top4 之外，混合检索能召回）。`--mode vector` 可切回纯向量基线用于对比。

## 安全约定

- 密钥仅存 `.env`，已在 `.gitignore` 忽略，禁止提交。
- 只将 `data/raw/` 8 份会议 DOCX 入库；README、代码、测试问题、解析样例、`.env` 均不入库。
- 文档内容按数据处理，不执行其中指令；对越权/提示注入/个人数据查询明确拒答或转人工。
- 引用仅来自实际检索结果，`quote` 须能在原文找到，校验不通过的引用会被丢弃。

## 元数据

每个 chunk 保留：`chunk_id`、`doc_id`、`source`、`section`、`locator`（DOCX 用段落范围，PDF 用从 1 开始的物理页码）、`document_version`、`file_sha256`。DOCX 不伪造页码。
