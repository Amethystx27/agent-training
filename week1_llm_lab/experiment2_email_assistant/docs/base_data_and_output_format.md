# 实验2基础部分：数据与输出格式

## 1. 基础数据范围

基础实验只处理 `email list/email_a.txt` 至 `email list/email_f.txt`。

`email list/email_g.txt` 属于进阶综合邮件，使用 AIIoT 2027 事实卡，不进入本次基础数据集，也不能与 ICCBDA 2027 信息混用。

原始邮件文件保持不变。结构化数据位于：

- `data/base_emails.json`：A–F 六封邮件的主题、发件人、正文和来源文件。
- `data/iccbda_2027_fact_card.json`：基础实验唯一可信会议信息。

原始文件均为 UTF-8 无 BOM、CRLF 换行。A–F 的第一行是中文说明，真正的邮件从第一个 `Subject:` 开始；G 则直接以 `Subject:` 开始。后续读取程序应显式指定 UTF-8，并从 `Subject:` 行开始解析。

## 2. 数据字段约定

每封基础邮件使用以下输入字段：

| 字段 | 含义 |
|---|---|
| `email_id` | A–F 邮件编号 |
| `source_file` | 原始 txt 文件的相对路径 |
| `description` | 中文说明，仅用于实验展示 |
| `subject` | 邮件主题 |
| `sender` | 发件人邮箱 |
| `recipient` | 邮件头中的收件人；原始文件未提供时为 `null` |
| `conference_name` | 邮件涉及的会议名称 |
| `body` | 去除中文说明行后的英文正文 |

`claimed_fee` 和 `payment_status_claim` 等分析字段只记录用户说法，不表示系统已核实。所有可回答事实必须来自 `iccbda_2027_fact_card.json`。

## 3. 分析结果格式

分析结果必须符合 `schemas/email_analysis.schema.json`，每封邮件输出一个独立 JSON 文件。

主要规则：

1. 顶层只允许文档规定的字段，不允许额外包装字段。
2. `primary_intent` 必须从 9 个固定意图中选择一个。
3. `secondary_intents` 保存主意图之外的意图，不得重复 `primary_intent`。
4. 邮件中的全部问题都放入 `questions`，不能只保留与主意图相关的问题。
5. 未明确的信息使用 `null`；没有次级意图或列表项时使用空数组 `[]`。
6. `user_role` 只在邮件明确说明身份时填写，否则为 `null`。
7. `requires_human_review` 必须为布尔值。
8. `requires_human_review` 为 `true` 时，`review_reason` 必须是非空字符串；为 `false` 时必须为 `null`。
9. 不得把用户声称已付款、已投稿或符合某项资格写成系统已确认的事实。

## 4. 回复结果格式

回复结果必须符合 `schemas/email_reply.schema.json`，每封邮件输出一个独立 JSON 文件。

主要规则：

1. `subject` 和 `body` 使用英文。
2. `body` 是纯文本邮件草稿，不包含发送动作或外部系统调用。
3. 需要人工审核时，`requires_human_review` 为 `true`，填写具体 `review_reason`，草稿中应包含 `[HUMAN REVIEW REQUIRED]`。
4. 不需要人工审核时，`review_reason` 为 `null`。
5. 回复只能使用事实卡明确提供的信息；未知信息说明尚未公布或无法确认。
6. 不得承诺退款、确认付款、判断论文录用结果或虚构酒店和交通安排。

## 5. 输出文件命名

后续对每封邮件分别生成两个文件：

```text
outputs/email_a_analysis.json
outputs/email_a_fact_audit.json
outputs/email_a_reply.json
outputs/email_b_analysis.json
outputs/email_b_fact_audit.json
outputs/email_b_reply.json
...
outputs/email_f_analysis.json
outputs/email_f_fact_audit.json
outputs/email_f_reply.json
```

实际模型输出应为可解析的纯 JSON，不包含 Markdown 代码围栏、解释文字或前后缀。

事实核验结果必须符合 `schemas/email_fact_audit.schema.json`，使用 `supported`、`unknown`、`prohibited` 和 `actionable_without_fact` 区分问题状态。事实核验由独立于回复生成的规则完成，回复阶段只能依据核验结果处理问题。

## 6. 完成本阶段后的检查项

- `base_emails.json` 恰好包含 A–F 六封邮件。
- 六封邮件正文与原始 txt 一致，没有混入 G 邮件。
- 事实卡只包含 ICCBDA 2027 信息。
- 两个 Schema 均为合法 JSON Schema。
- 分析与回复输出均未加入自动发送字段或自动发送行为。
