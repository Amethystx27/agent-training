import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Optional
from pydantic import BaseModel, ValidationError

# 1. 定义质检标准
class OtherDate(BaseModel):
    type: str
    date: str

class RegistrationFee(BaseModel):
    category: str
    amount: float 
    currency: str

class ConferenceInfo(BaseModel):
    conference_name: Optional[str] = None
    conference_full_name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    topics: Optional[List[str]] = None
    submission_deadline: Optional[str] = None
    other_dates: Optional[List[OtherDate]] = None
    registration_fee: Optional[List[RegistrationFee]] = None
    organizer: Optional[str] = None

load_dotenv("../.env")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL"))

# 2. 读取本地 notice_b.txt 文件
print("=== 正在读取 notice_b.txt ===")
with open("notice_b.txt", "r", encoding="utf-8") as f:
    notice_text = f.read()

prompt = """
你是一名学术会议信息抽取助手。
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
8. 请严格按照以下 JSON 结构输出，不要改变字段名：
{
  "topics": ["主题1", "主题2"],
  "other_dates": [{"type": "日期类型", "date": "YYYY-MM-DD"}],
  "registration_fee": [{"category": "适用人群", "amount": 0, "currency": "币种"}]
}
9. 即使原文没有出现 "Topics:" 字段，也要从投稿邀请的段落中提取具体的研究主题词，填入 topics 数组。
"""

# 3. 调用模型
response = client.chat.completions.create(
    model=os.getenv("MODEL_NAME"),
    messages=[{"role": "system", "content": prompt}, {"role": "user", "content": notice_text}],
    temperature=0.1
)
raw_output = response.choices[0].message.content

# 4. 清洗与质检
print("\n=== 模型原始输出 ===")
print(raw_output)
clean_json_str = raw_output.strip().replace("```json", "").replace("```", "")

print("\n=== 质检开始 ===")
try:
    parsed_data = json.loads(clean_json_str)
    conf = ConferenceInfo(**parsed_data)
    print("✅ 质检通过！格式完全符合。")
    print("提取到的会议名称：", conf.conference_name)
except ValidationError as e:
    print("❌ 格式质检失败！模型给的格式违规：\n", e)
except json.JSONDecodeError:
    print("❌ 解析失败！模型连合法的 JSON 都没给出。")