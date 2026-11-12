import json
import os
import re
from datetime import date
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from common import chat, extract_json


SYSTEM_PROMPT = """你是一名学术会议信息抽取助手。
请仅依据用户提供的会议通知提取信息，不得使用外部知识补全或猜测。

输出字段：
conference_name, conference_full_name, start_date, end_date,
location, topics, submission_deadline, other_dates,
registration_fee, organizer。

规则：
1. 所有字段必须出现；缺失值使用 null。
2. 日期统一为 YYYY-MM-DD。
3. submission_deadline 仅填写明确的全文投稿截止日期。
4. 其他日期按类型放入 other_dates。
5. 费用必须保留币种和适用人群。
6. 不确定、缺失或有歧义的信息不得自行推断。
7. 只输出合法 JSON，不要输出 Markdown 代码围栏或解释。

请严格遵循以下 JSON 格式示例：
{
  "conference_name": "会议简称",
  "conference_full_name": "会议全称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "location": "地点",
  "topics": ["主题1", "主题2"],
  "submission_deadline": "YYYY-MM-DD",
  "other_dates": [
    {"type": "acceptance_notification", "date": "YYYY-MM-DD"}
  ],
  "registration_fee": [
    {"category": "Student Author", "amount": 350, "currency": "USD"}
  ],
  "organizer": "主办方"
}"""


def _check_date_string(v: Optional[str]):
    if v is None:
        return v
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        raise ValueError(f"日期格式错误: {v}")
    date.fromisoformat(v)
    return v


class OtherDate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    date: str

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        return _check_date_string(v)


class RegistrationFee(BaseModel):
    model_config = ConfigDict(extra="ignore")
    category: str
    amount: float
    currency: str

    @field_validator("category", mode="before")
    @classmethod
    def extract_category(cls, v, info):

        if v is None and "audience" in info.data:
            return info.data["audience"]
        return v

    @field_validator("amount", "currency", mode="before")
    @classmethod
    def parse_fee(cls, v, info):

        fee_str = info.data.get("fee") if info.data else None
        if fee_str and isinstance(fee_str, str):
            parts = fee_str.split()
            if len(parts) == 2:
                if info.field_name == "currency":
                    return parts[0]
                if info.field_name == "amount":
                    try:
                        return float(parts[1])
                    except ValueError:
                        pass
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if v < 0:
            raise ValueError("费用金额不能为负")
        return v


class ConferenceInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")  # 改为 ignore

    conference_name: Optional[str] = None
    conference_full_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    submission_deadline: Optional[str] = None
    other_dates: List[OtherDate] = Field(default_factory=list)
    registration_fee: Optional[Union[List[RegistrationFee], RegistrationFee]] = None
    organizer: Optional[str] = None

    @field_validator("start_date", "end_date", "submission_deadline")
    @classmethod
    def validate_dates(cls, v):
        return _check_date_string(v)

    @field_validator("other_dates", mode="before")
    @classmethod
    def format_other_dates(cls, v):
        if v is None:
            return []
        if isinstance(v, dict):
            return [{"type": k, "date": val} for k, val in v.items()]
        return v


REQUIRED_FIELDS = {
    "conference_name",
    "conference_full_name",
    "start_date",
    "end_date",
    "location",
    "topics",
    "submission_deadline",
    "other_dates",
    "registration_fee",
    "organizer",
}


def extract_conference_info(text: str) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"会议通知原文：\n{text}"},
    ]
    resp = chat(messages, response_format={"type": "json_object"})
    raw_text = resp.choices[0].message.content
    raw_json = extract_json(raw_text)
    return {"raw_text": raw_text, "raw_json": raw_json}


def validate_conference_info(raw_json: Dict[str, Any]) -> ConferenceInfo:
    keys = set(raw_json.keys())
    missing = REQUIRED_FIELDS - keys
    extra = keys - REQUIRED_FIELDS
    if missing:
        raise ValueError(f"缺少字段: {missing}")
    if extra:
        raise ValueError(f"多余字段: {extra}")
    return ConferenceInfo.model_validate(raw_json)


TEXTS = {
    "A": """ICCBDA 2027 Call for Papers
The 11th International Conference on Cloud Computing and Big Data Analytics (ICCBDA 2027)
Date: May 21–23, 2027
Venue: Xihua University, Chengdu, China

ICCBDA 2027 invites researchers, engineers, and practitioners to submit original papers on cloud computing, big data analytics, artificial intelligence, edge computing, distributed systems, and related areas.

Important Dates:
- Paper Submission Deadline: February 15, 2027
- Notification of Acceptance: March 25, 2027
- Camera-ready Paper: April 15, 2027
- Conference Dates: May 21–23, 2027

Registration Fees:
- Student Author: USD 350
- Regular Author: USD 450
- Listener: USD 180

The conference is organized by the School of Computer and Software Engineering, Xihua University.
For inquiries, please contact iccbda2027@example.org.
""",
    "B": """Edge Intelligence Forum 2027
Edge Intelligence Forum 2027 will take place in Chengdu, China, in October 2027.

The forum welcomes submissions on edge intelligence, federated learning, Internet of Things, and network security. Authors should submit manuscripts through the online submission portal.

The submission deadline is expected to be announced soon. Registration information will be published on the official website.

The event is supported by the Center for Distributed Intelligence.
""",
    "C": """International Workshop on Smart Networks 2027
The International Workshop on Smart Networks 2027 will be held in Singapore on November 12–13, 2027.

Important dates:
- Abstract registration deadline: July 10, 2027
- Full paper submission deadline: July 24, 2027
- Acceptance notification: September 5, 2027
- Early-bird registration deadline: October 1, 2027

Topics include intelligent networking, edge computing, network automation, and AI-enabled network management.

The registration fee is SGD 300 for students and SGD 480 for regular participants.
""",
}


def main():
    os.makedirs("outputs", exist_ok=True)
    for key, text in TEXTS.items():
        print(f"\n===== 通知 {key} =====")
        try:
            result = extract_conference_info(text)
            try:
                validated = validate_conference_info(result["raw_json"])
                valid = True
                error = None
                validated_json = validated.model_dump()
            except (ValidationError, ValueError) as e:
                valid = False
                error = str(e)
                validated_json = None

            output = {
                "input_key": key,
                "raw_model_output": result["raw_text"],
                "parsed_json": result["raw_json"],
                "valid": valid,
                "validation_error": error,
                "validated_json": validated_json,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))

            with open(f"outputs/exp1_{key}.json", "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"通知 {key} 处理失败: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()