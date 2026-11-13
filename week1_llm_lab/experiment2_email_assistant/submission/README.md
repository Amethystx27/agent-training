# 实验2提交材料

本目录汇总实验2的基础和进阶邮件处理材料。基础实验过程和结果见 `实验2总结.md`，AIIoT 2027 进阶实验见 `实验2进阶实验总结.md`。

## 材料索引

| 材料 | 位置 | 用途 |
|---|---|---|
| 实验要求 | `../实验2 会议邮件智能回复助手.docx` | 原始实验说明 |
| 基础邮件 A–F | `../email list/email_a.txt` 至 `../email list/email_f.txt` | 原始输入 |
| 结构化邮件数据 | `../data/base_emails.json` | 去除中文说明行后的主题、发件人和正文 |
| 会议事实卡 | `../data/iccbda_2027_fact_card.json` | 唯一可信会议事实 |
| 事实核验规则 | `../data/fact_audit_policy.json` | 逐问题核验和人工审核依据 |
| 分析 Prompt | `../prompts/analysis_system.md` | 邮件分类和信息提取 |
| 回复 Prompt | `../prompts/reply_system.md` | 受事实约束的英文草稿生成 |
| 批处理源代码 | `../scripts/run_base_experiment.py` | A–F 分析和回复生成 |
| 输出验证源代码 | `../scripts/validate_outputs.py` | 结构和审核一致性验证 |
| JSON Schema | `../schemas/` | 分析、事实核验和回复格式定义 |
| 逐封分析结果 | `../outputs/email_a_analysis.json` 至 `../outputs/email_f_analysis.json` | 意图、问题和实体提取 |
| 逐封事实核验 | `../outputs/email_a_fact_audit.json` 至 `../outputs/email_f_fact_audit.json` | 支持、未知、禁止和可操作分类 |
| 逐封英文草稿 | `../outputs/email_a_reply.json` 至 `../outputs/email_f_reply.json` | 英文回复和审核标记 |
| 回复汇总 | `../outputs/draft_replies.md` | 便于人工阅读的六封回复 |
| 事实核验汇总 | `../outputs/fact_audit_summary.md` | 全部问题的核验表 |
| 实验总结 | `实验2总结.md` | 实验方法、结果、完成状态和问题反思 |
| 实验说明指南 | `实验说明指南.md` | 全部文件夹、文件用途、阅读顺序和复现命令 |
| 运行结果图 | `run_evidence.png` | 根据实际运行摘要渲染的提交证据 |
| 进阶邮件 G | `../email list/email_g.txt` | AIIoT 2027 注册、住宿和发票综合咨询 |
| 进阶事实卡 | `../data/aiiot_2027_fact_card.json` | AIIoT 2027 唯一可信事实 |
| 进阶 Prompt | `../prompts/advanced_*.md` | 单标签、多标签、信息提取和三风格回复 Prompt |
| 进阶源代码 | `../scripts/run_advanced_experiment.py` | 进阶实验运行流程 |
| 进阶验证代码 | `../scripts/validate_advanced_outputs.py` | 分类、提取、核验和回复一致性验证 |
| 进阶结果 | `../outputs/advanced_*` | 分类、提取、核验、三风格回复和比较结果 |
| 进阶实验总结 | `实验2进阶实验总结.md` | AIIoT 2027 进阶实验方法、结果和结论 |

`email_g.txt` 是 AIIoT 2027 进阶邮件，不纳入基础实验。基础事实卡中也不包含 AIIoT 信息。

## 复现步骤

在 `experiment2_email_assistant` 目录执行：

```powershell
python -B scripts/run_base_experiment.py
python -B scripts/validate_outputs.py
python -B scripts/run_advanced_experiment.py
python -B scripts/validate_advanced_outputs.py
```

运行脚本会从上一级 `week1_llm_lab/.env` 读取 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `MODEL_NAME`。密钥只保存在内存中，不复制到本实验目录，也不写入输出文件。

`outputs/run_summary.json` 是运行脚本动态生成的临时调用摘要，已加入 `.gitignore`，不属于仓库提交内容。`validate_outputs.py` 只验证现有结果并输出报告，不创建额外文件。

## 交付边界

系统只生成英文回复草稿，不连接邮件发送服务，不自动发送邮件。B、C、E 三封邮件的草稿必须经过人工审核后才能进入实际业务。
