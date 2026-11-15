from openai import OpenAI
from config import API_BASE_URL, API_KEY, MODEL_NAME

_client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)


def chat(system_prompt: str, user_content: str,
         temperature: float = 0.0, use_json_mode: bool = False) -> str:
    kwargs = dict(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=temperature,
    )
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = _client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content


def chat_with_tools(messages, tools, tool_choice="auto", temperature: float = 0.0):
    """Function Calling 用：返回完整 message 对象（含 tool_calls）。"""
    resp = _client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
    )
    return resp.choices[0].message