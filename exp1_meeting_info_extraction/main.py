"""
实验1：会议通知智能信息提取
============================
读取会议通知文本 -> 调用大模型 -> 输出规范 JSON
提取字段：会议名称 / 举办日期 / 地点 / 主题 / 投稿截止日期 / 注册费用

作业要求：
  - 输出合法 JSON，前后不得附加任何解释文字
  - 文本中未明确提供的信息一律用 null，严禁模型猜测
  - 日期统一为 YYYY-MM-DD；费用保留 币种 / 金额 / 适用类别
  - 程序必须解析 JSON 并校验：字段完整性、日期格式、数据类型

运行方式：
  1) 安装依赖:  pip install -r requirements.txt
  2) 配置密钥:  复制 .env.example 为 .env，填入导师给的 API_KEY / API_BASE / MODEL
  3) 运行:      python main.py sample_meeting_notice.txt
  4) 无密钥自测: python main.py --mock     （跳过 API，只验证解析+校验逻辑）
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---- 可选依赖：python-dotenv（用于读取 .env）----
try:
    from dotenv import load_dotenv
    HAVE_DOTENV = True
except ImportError:
    HAVE_DOTENV = False

# ---- 必需依赖：pydantic（用于结构化校验）----
try:
    from pydantic import BaseModel, field_validator
    HAVE_PYDANTIC = True
except ImportError:
    HAVE_PYDANTIC = False
    print("[警告] 未检测到 pydantic，请先执行: pip install -r requirements.txt",
          file=sys.stderr)


# ============ 1. 数据模型与校验 ============
class RegistrationFee(BaseModel):
    currency: str
    amount: float
    category: Optional[str] = None


class MeetingInfo(BaseModel):
    conference_name: Optional[str] = None
    date: Optional[str] = None
    location: Optional[str] = None
    theme: Optional[str] = None
    submission_deadline: Optional[str] = None
    registration_fee: Optional[RegistrationFee] = None

    @field_validator("date", "submission_deadline")
    @classmethod
    def _check_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v or ""):
            raise ValueError(f"日期必须为 YYYY-MM-DD，收到: {v!r}")
        # 进一步校验是否为真实存在的日期（如 2027-13-45 会在此失败）
        datetime.strptime(v, "%Y-%m-%d")
        return v


# ============ 2. 调用大模型 ============
def call_llm(notice_text: str) -> str:
    """调用兼容 OpenAI 接口的大模型（DeepSeek / Qwen 均可），返回原始文本。"""
    from openai import OpenAI  # 仅在真正调用时才导入，方便无密钥时也能跑 --mock

    client = OpenAI(
        api_key=os.environ["API_KEY"],
        base_url=os.environ.get("API_BASE"),  # 例如 https://api.deepseek.com/v1
    )
    model = os.environ.get("MODEL", "deepseek-chat")

    system_prompt = (
        "你是一个会议信息提取助手。请从用户提供的会议通知文本中提取以下字段，"
        "并以单个 JSON 对象返回，禁止输出 JSON 之外的任何解释、注释或代码块标记：\n"
        "conference_name(会议名称, 字符串)\n"
        "date(会议举办日期, 字符串 YYYY-MM-DD)\n"
        "location(举办地点, 字符串)\n"
        "theme(会议主题, 字符串)\n"
        "submission_deadline(投稿/注册截止日期, 字符串 YYYY-MM-DD)\n"
        "registration_fee(注册费用对象: {currency 币种, amount 金额数字, category 适用类别})\n"
        "硬性规则：\n"
        "1) 文本中未明确给出的信息一律填 null，绝对禁止猜测或补全；\n"
        "2) 日期必须格式化为 YYYY-MM-DD；\n"
        "3) registration_fee 必须是对象或 null，不得写成字符串；\n"
        "4) 只输出 JSON，不要 Markdown 代码块、不要前后说明。"
    )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": notice_text},
        ],
        response_format={"type": "json_object"},  # 强制模型输出 JSON
        temperature=0,
    )
    return resp.choices[0].message.content


# ============ 3. 解析与校验 ============
def parse_and_validate(raw: str) -> dict:
    """把模型返回的字符串解析为 JSON，并用 Pydantic 校验字段/日期/类型。"""
    raw = raw.strip()
    # 容错：如果模型仍包裹了 ```json 代码块，提取其中最外层的 {}
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"模型返回的不是合法 JSON: {e}\n原始内容: {raw}")
    # Pydantic 校验：字段名、日期格式、数据类型不符会抛 ValidationError
    info = MeetingInfo(**data)
    return info.model_dump()


# ============ 4. 自测样例（无需 API Key）============
MOCK_OUTPUT = {
    "conference_name": "ICCBDA 2027",
    "date": "2027-04-15",
    "location": "Beijing, China",
    "theme": "Big Data and Analytics",
    "submission_deadline": "2026-12-01",
    "registration_fee": {"currency": "USD", "amount": 500.0, "category": "Regular"},
}


# ============ 5. 入口 ============
def main() -> None:
    if not HAVE_PYDANTIC:
        sys.exit("缺少 pydantic，无法运行。请执行: pip install -r requirements.txt")

    ap = argparse.ArgumentParser(description="会议通知智能信息提取（实验1）")
    ap.add_argument("input", nargs="?", help="会议通知文本文件路径")
    ap.add_argument("--mock", action="store_true",
                    help="不调用 API，用内置样例验证解析+校验流程")
    args = ap.parse_args()

    if HAVE_DOTENV:
        load_dotenv()

    if args.mock:
        raw = json.dumps(MOCK_OUTPUT, ensure_ascii=False)
        print("[mock] 使用内置样例，跳过 API 调用")
    else:
        if not args.input:
            ap.error("请提供会议通知文本文件，或使用 --mock 自测")
        notice = Path(args.input).read_text(encoding="utf-8")
        raw = call_llm(notice)

    try:
        result = parse_and_validate(raw)
    except (ValueError, Exception) as e:  # ValidationError 继承 ValueError
        sys.exit(f"[校验失败] {e}")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
