# 实验1/2：会议知识库与检索增强问答

本目录包含第二周实验1和实验2。实验1完成DOCX解析、章节切分、稳定chunk、
真实Embedding、FAISS持久化和独立进程检索；实验2在此基础上实现检索增强问答、
结构化引用和引用校验。

## 目录

```text
test1/
  data/raw/              # 8份学生会议DOCX
  data/chunks.jsonl      # 33个已生成chunk
  data/experiment2_questions.json # 实验2首轮验证问题
  evaluation/             # 实验3题库、事实清单、同伴问题和注入样例
  src/rag.py             # 解析、切分、Embedding客户端及FAISS接口
  src/rag_qa.py          # 实验2检索增强问答与引用校验
  src/rag_experiment3.py # 实验3评测、拒答指标和参数对比
  prompts/               # 实验2系统Prompt和用户模板
  tests/test_rag.py      # 7项离线测试
  tests/test_rag_qa.py   # 实验2离线测试
  tests/test_rag_experiment3.py # 实验3评测组件测试
  results/               # 原始清单、解析统计、异常日志
  results/experiment2/   # 实验2检索过程、模型响应和逐题结果
  results/experiment3/   # 28题、两档参数、同伴和注入测试结果
  index/                 # 正式FAISS索引和manifest
  requirements.txt
  requirements-lock.txt
  .venv/                 # Python 3.12虚拟环境，不提交
  .env.example           # 空占位配置，可提交
  .env                   # 本地真实配置，不提交
```

## 已完成内容

- 8份会议DOCX已移动到 `data/raw/`。
- 解析器支持DOCX标题、正文、表格原文顺序，以及PDF逐页文本。
- DOCX使用真实段落范围定位，不伪造页码；PDF使用从1开始的物理页码。
- 按标题形成章节块，再使用 `chunk_size=600`、`chunk_overlap=100`切分。
- chunk包含稳定 `chunk_id`、来源、章节、段落范围、版本和文件哈希。
- 已生成33个chunk，33个ID均唯一。
- 已实现OpenAI兼容Embedding客户端、批次和维度检查、FAISS持久化和可信索引重载。
- 已生成Python 3.12虚拟环境及 `requirements-lock.txt`。
- 7项离线测试全部通过，包括真实DOCX表格、空文档错误、文档版本、稳定ID、
  JSONL往返、FAISS重载和源文件变更后的旧索引失效。
- 真实Embedding模型 `text-embedding-v3` 返回1024维向量。
- 正式FAISS索引包含33个向量，已从独立Python进程成功重载并检索。

## 原始资料摘要

- 文件数：8，全部为DOCX。
- 总大小：662,630字节，8个SHA-256均唯一。
- Word段落：82；Word表格：0；PDF：0。
- 解析统计：33个章节/定位单元，0个空文本，0个错误或警告。
- chunk：33个，最短59字符、最长149字符、平均110.06字符。
- 入库边界：只允许 `data/raw/` 中的8份DOCX进入知识库。

完整数据见：

- `results/raw_inventory.csv`
- `results/parse_stats.json`
- `results/parse_errors.log`
- `data/chunks.jsonl`

## 环境

- Python：3.12.10。
- 依赖导入和 `pip check`：通过。
- FAISS：1.16.0 CPython 3.12 wheel。
- `.env` 已被父级和项目 `.gitignore` 忽略。
- `.env.example` 只保留空值和可选参数，不含真实凭据。

Embedding客户端支持以下配置：

```text
EMBEDDING_API_KEY
EMBEDDING_BASE_URL
EMBEDDING_MODEL
EMBEDDING_BATCH_SIZE=10
EMBEDDING_TIMEOUT=60
```

密钥或Base URL未单独配置时，客户端可回退到 `OPENAI_API_KEY` 和
`OPENAI_BASE_URL`；`EMBEDDING_MODEL` 必须明确配置，不能复用生成模型名。

接口单批次最多支持10条文本，已按该限制配置并完成33个chunk的四次批量请求。
当前正式索引位于 `index/`，由 `index.faiss`、`index.pkl` 和 `manifest.json` 组成。

## 命令

重建解析结果和chunks：

```powershell
.\.venv\Scripts\python.exe -m src.rag prepare
```

在Embedding接口确认后构建索引：

```powershell
.\.venv\Scripts\python.exe -m src.rag index
```

加载索引并查询：

```powershell
.\.venv\Scripts\python.exe -m src.rag query "学生作者早鸟价格是多少？" --k 4
```

回答单个问题并保留完整追踪：

```powershell
.\.venv\Scripts\python.exe -m src.rag_qa ask "最终全文截止？摘要也延期吗？" --top-k 4
```

运行实验2首轮六题：

```powershell
.\.venv\Scripts\python.exe -m src.rag_qa batch data\experiment2_questions.json --output results\experiment2\rag_answers.json --top-k 4
```

运行实验3的28题：

```powershell
.\.venv\Scripts\python.exe -m src.rag_experiment3 run --top-k 4 --output results\experiment3\top_k_4.json
```

比较两档top_k：

```powershell
.\.venv\Scripts\python.exe -m src.rag_experiment3 compare results\experiment3\top_k_2.json results\experiment3\top_k_4.json --output results\experiment3\comparison.json
```

运行同伴未见问题、隔离注入和冲突测试：

```powershell
.\.venv\Scripts\python.exe -m src.rag_experiment3 peer --top-k 4 --output results\experiment3\peer_test.json
.\.venv\Scripts\python.exe -m src.rag_experiment3 injection --output results\experiment3\injection_test.json
.\.venv\Scripts\python.exe -m src.rag_experiment3 conflict --output results\experiment3\conflict_test.json
```

运行离线测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 当前限制

- 8份正式DOCX包含0个Word表格；表格解析目前由合成测试覆盖。
- 当前没有PDF样本，`pypdf`逐页路径尚不能使用正式资料验收。
- 实验3已完成28题评价、两档top_k对比、同伴问题、提示注入和冲突转人工测试。
- 当前LLM为推理型接口，回答调用预留较大输出预算；空正文或引用无效时标记人工复核。
- 事实正确性和引用支持由同一模型接口离线评判，仍属于自动化评价结果，不代表独立人工复核。

正式验证结果见 `results/experiment1_verification.json`、`results/experiment2/`和`results/experiment3/`。

