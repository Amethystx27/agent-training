TOOLS = [
    {"type": "function", "function": {
        "name": "get_current_time",
        "description": "查询指定 IANA 时区的当前时间",
        "parameters": {"type": "object", "properties": {
            "timezone": {"type": "string", "description": "例如 Asia/Singapore"}
        }, "required": ["timezone"]},
    }},
    {"type": "function", "function": {
        "name": "days_until",
        "description": "计算距离指定日期还有多少天",
        "parameters": {"type": "object", "properties": {
            "target_date": {"type": "string", "description": "YYYY-MM-DD"}
        }, "required": ["target_date"]},
    }},
    {"type": "function", "function": {
        "name": "get_conference_deadline",
        "description": "按会议名称查询模拟会议截止日期",
        "parameters": {"type": "object", "properties": {
            "conference_name": {"type": "string", "description": "例如 ICCBDA 2027"}
        }, "required": ["conference_name"]},
    }},
    {"type": "function", "function": {
        "name": "search_conference",
        "description": "按会议名称查询会议详情（起止时间、地点、投稿截止、主题）",
        "parameters": {"type": "object", "properties": {
            "conference_name": {"type": "string"}
        }, "required": ["conference_name"]},
    }},
    {"type": "function", "function": {
        "name": "convert_timezone",
        "description": "把带明确日期时间从一个时区转换到另一个时区，自动处理夏令时",
        "parameters": {"type": "object", "properties": {
            "datetime_str": {"type": "string", "description": "ISO 时间，如 2027-05-01T09:00:00"},
            "from_tz": {"type": "string", "description": "IANA 时区"},
            "to_tz": {"type": "string", "description": "IANA 时区"}
        }, "required": ["datetime_str", "from_tz", "to_tz"]},
    }},
    {"type": "function", "function": {
        "name": "get_timezone_for_city",
        "description": "把城市名（中英文）映射为 IANA 时区",
        "parameters": {"type": "object", "properties": {
            "city": {"type": "string", "description": "例如 东京 / New York"}
        }, "required": ["city"]},
    }},
]