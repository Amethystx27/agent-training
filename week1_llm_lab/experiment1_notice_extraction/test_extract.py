import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# 加载上一层的 .env 文件
load_dotenv("../.env")

# 初始化客户端（因为你在 One API 配了重定向，填 chat 或 flash 都能通）
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

notice_a = """
The 11th International Conference on Cloud Computing and Big Data Analytics (ICCBDA 2027)
Date: May 21–23, 2027
Venue: Xihua University, Chengdu, China
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
"""

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

try:
    response = client.chat.completions.create(
        model=os.getenv("MODEL_NAME"), # 用你 .env 里当前配的模型
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": notice_a}
        ],
        temperature=0.1 
    )
    
    raw_output = response.choices[0].message.content
    print("=== 模型原始输出 ===")
    print(raw_output)
    
    print("\n=== 解析测试 ===")
    try:
        data = json.loads(raw_output)
        print("解析成功！提取到 conference_name:", data.get("conference_name"))
    except Exception as parse_error:
        print("解析失败！报错信息：", parse_error)

except Exception as e:
    print("API 请求报错：", e)