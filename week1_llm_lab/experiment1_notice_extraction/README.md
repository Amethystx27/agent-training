# 实验1：会议通知智能信息提取

本实验读取三份固定的会议通知文本，调用兼容 OpenAI Chat Completions 接口的大模型提取结构化信息，并使用 Pydantic 执行严格校验。程序支持两版 Prompt、A/B/C 批量运行和离线试运行。

## 文件说明

```text
experiment1_notice_extraction/
├── notice_a.txt                 # 信息完整的会议通知
├── notice_b.txt                 # 缺失日期、费用等信息的会议通知
├── notice_c.txt                 # 包含多类日期的会议通知
├── notice_d.txt                 # AIIoT 2027 进阶通知
├── prompts.py                   # Prompt V1 和 V2
├── schemas.py                   # Pydantic 数据模型和校验规则
├── validate_schema.py           # 统一运行入口
├── advanced_prompts.py          # 进阶 Prompt V1 和 V2
├── advanced_schemas.py          # 进阶费用和注册政策模型
├── advanced_extract.py          # 进阶任务运行入口
├── test_extract.py              # 兼容旧命令的入口包装
├── requirements.txt             # Python 依赖
├── outputs/                     # 校验后的 JSON 和原始模型响应
├── render_result_screenshots.ps1 # 基础任务结果截图
└── render_advanced_screenshots.ps1 # 进阶任务结果截图
```

## 环境变量

程序优先读取当前实验目录的 `.env`，随后读取上一级项目目录的 `.env`。需要配置：

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://your-api-base/v1
MODEL_NAME=your_model_name
```

`.env` 包含敏感凭据，不应提交到 Git，也不要将真实 API Key 写入代码、README、结果文件或截图。

## 安装依赖

推荐使用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果当前环境已经安装依赖，也可以直接检查：

```powershell
python -m pip install -r requirements.txt
```

## 运行方式

脚本会根据参数读取实验目录内的固定通知文件，不依赖当前终端中手工输入通知文本。

运行单个通知和单个 Prompt：

```powershell
python validate_schema.py --notice a --prompt-version 1
python validate_schema.py --notice b --prompt-version 2
python validate_schema.py --notice c --prompt-version 2
```

运行 A/B/C 与两个 Prompt 的全部组合：

```powershell
python validate_schema.py --notice all --prompt-version all
```

该命令会执行 6 次模型调用，并生成：

```text
outputs/
├── notice_a_prompt_v1.json
├── notice_a_prompt_v2.json
├── notice_b_prompt_v1.json
├── notice_b_prompt_v2.json
├── notice_c_prompt_v1.json
├── notice_c_prompt_v2.json
└── raw/
    ├── notice_a_prompt_v1.txt
    ├── notice_a_prompt_v2.txt
    ├── notice_b_prompt_v1.txt
    ├── notice_b_prompt_v2.txt
    ├── notice_c_prompt_v1.txt
    └── notice_c_prompt_v2.txt
```

兼容入口也可以使用相同参数：

```powershell
python test_extract.py --notice c --prompt-version 1
```

## 离线试运行

`--dry-run` 只检查通知文件读取和 Prompt 选择，不会调用模型：

```powershell
python validate_schema.py --dry-run --notice a --prompt-version 2
python validate_schema.py --dry-run --notice all --prompt-version all
```

如果需要查看完整 Prompt：

```powershell
python validate_schema.py --dry-run --notice c --prompt-version 1 --show-prompt
```

## 校验规则

程序要求所有字段必须出现，但字段值允许为 `null`，并执行以下检查：

- 禁止额外字段。
- 日期必须是真实存在的 `YYYY-MM-DD` 日期。
- 起止日期同时存在时，开始日期不能晚于结束日期。
- 费用金额必须是有限正数，字符串金额会被拒绝。
- 币种必须是三位字母代码，并规范为大写。
- 禁止重复主题、重复收费类别及重复日期条目。
- `other_dates.type` 只能使用约定类型。

如果模型输出 Markdown JSON 围栏，解析器会提取其中的 JSON；顶层必须是 JSON 对象。

## 运行截图

`render_result_screenshots.ps1` 读取 `outputs/` 中本次真实运行的原始响应和校验结果，生成四张 PNG：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\render_result_screenshots.ps1
```

该脚本不会调用模型 API。

## AIIoT 2027 进阶任务

进阶任务使用 `notice_d.txt`，单独验证三类参会者和两个收费阶段：

```powershell
python advanced_extract.py --dry-run --prompt-version all
python advanced_extract.py --prompt-version 1
python advanced_extract.py --prompt-version 2
python advanced_extract.py --prompt-version all
```

运行结果保存为：

```text
outputs/
├── notice_d_prompt_v1.json
├── notice_d_prompt_v2.json
└── raw/
    ├── notice_d_prompt_v1.txt
    └── notice_d_prompt_v2.txt
```

进阶校验会确认：

- `regular_author`、`student_author`、`non_author_participant` 三类参会者均存在。
- `early_bird` 和 `regular` 两个阶段均有费用。
- 六种类别与收费阶段组合恰好完整，没有缺失或重复。
- 所有费用使用同一币种。
- 每个类别的早鸟价低于普通价。
- 早鸟费用的截止日期与顶层早鸟截止日期一致。
- 学生资格、证明材料、注册条件、费用包含项和排除项均已提取。

生成进阶截图：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\render_advanced_screenshots.ps1
```

该脚本同样不会调用模型 API。详细结果见 `进阶实验总结.md`。
