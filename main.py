import os
import json
from datetime import date
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel,Field,field_validator,ValidationError
from typing import List,Optional

class DateItem(BaseModel):
    type: str
    date: str
    @field_validator("date")
    def check_date_format(cls, v):
        date.fromisoformat(v)
        return v
    
class FeeItem(BaseModel):
    category: str
    amount: float
    currency: str

class ConferenceInfo(BaseModel):
    conference_name: str
    conference_full_name: str
    start_date: str
    end_date: str
    location: Optional[str]
    topics: List[str]
    submission_deadline: str
    other_dates: List[DateItem]
    registration_fee: List[FeeItem]
    organizer: Optional[str]

    @field_validator("start_date", "end_date", "submission_deadline")
    def check_iso_date(cls, v):
        date.fromisoformat(v)
        return v
    
load_dotenv()
client =OpenAI(
    api_key="sk-mQ5jk2w75tpiGgZi232d06Cc79E6487fB8Cf54382cEcAc75",
    base_url="http://43.142.146.132:8000/v1",
)
input_text="""
The International Workshop on Smart Networks 2027 will be held in Singapore on November 12–13, 2027.
Important dates:
- Abstract registration deadline: July 10, 2027
- Full paper submission deadline: July 24, 2027
- Acceptance notification: September 5, 2027
- Early-bird registration deadline: October 1, 2027
Topics include intelligent networking, edge computing, network automation, and AI-enabled network management.
The registration fee is SGD 300 for students and SGD 480 for regular participants.
"""
instruction="""
你是一名学术会议信息抽取助手。
请仅依据用户提供的会议通知提取信息，不得使用外部知识补全或猜测。
"""
output="""
所有字段必须出现；缺失值使用 null,日期统一为 YYYY-MM-DD,submission_deadline 仅填写明确的全文投稿截止日期,
其他日期按类型放入 other_dates,费用必须保留币种和适用人群,不确定、缺失或有歧义的信息不得自行推断,
只输出合法 JSON，不要输出 Markdown 代码围栏或解释。
"""
examples="""
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
{
  "conference_name": "ICCBDA 2027",
  "conference_full_name": "The 11th International Conference on Cloud Computing and Big Data Analytics",
  "start_date": "2027-05-21",
  "end_date": "2027-05-23",
  "location": "Xihua University, Chengdu, China",
  "topics": ["Cloud Computing", "Big Data Analytics",
    "Artificial Intelligence", "Edge Computing", "Distributed Systems"],
  "submission_deadline": "2027-02-15",
  "other_dates": [
    {"type": "acceptance_notification", "date": "2027-03-25"},
    {"type": "camera_ready", "date": "2027-04-15"}
  ],
  "registration_fee": [
    {"category": "Student Author", "amount": 350, "currency": "USD"},
    {"category": "Regular Author", "amount": 450, "currency": "USD"},
    {"category": "Listener", "amount": 180, "currency": "USD"}
  ],
  "organizer": "School of Computer and Software Engineering, Xihua University"
}
"""
prompt=f"""
{instruction}
{output}
{examples}
{input_text}
"""
response = client.chat.completions.create(
    model="deepseek-flash",
    messages=[
        {"role": "system", "content": prompt},
        {"role": "user", "content": "提取会议信息"},
    ],
    stream=False,
    response_format={"type":"json_object"},
    extra_body={"thinking": {"type": "enabled"}},
)
R=response.choices[0].message.content
Record={
    "original_text": input_text,
    "model_raw_output": R,
    "json_parse_status": None,
    "pydantic_validate_status": None,
    "parsed_dict": None,
    "validated_data": None,
    "error_msg": None
}
try:
    result=json.loads(R)
    Record["json_parse_status"]="success"
    Record["parsed_dict"]=result
    conf = ConferenceInfo(**result)
    Record["pydantic_validate_status"] = "success"
    Record["validated_data"] = conf.model_dump()
    print(json.dumps(conf.model_dump(), indent=2, ensure_ascii=False))

except json.JSONDecodeError as err:
    Record["json_parse_status"] = "fail"
    Record["error_msg"] = f"JSON解析失败：{str(err)}"
    print(err)

except ValidationError as err:
    Record["json_parse_status"] = "success"
    Record["pydantic_validate_status"] = "fail"
    Record["error_msg"] = f"Pydantic校验失败：{str(err)}"
    print(err)

print(json.dumps(Record, indent=2, ensure_ascii=False))
