TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "查询指定城市或 IANA 时区的当前时间。城市支持中英文（如 新加坡 / Singapore / 东京 / Tokyo）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "城市名（中文或英文）或 IANA 时区，如 Singapore、Asia/Tokyo、纽约",
                    }
                },
                "required": ["timezone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "days_until",
            "description": "计算从今天到指定日期还有多少天。返回正数表示未来，负数表示已过去。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_date": {
                        "type": "string",
                        "description": "目标日期，格式 YYYY-MM-DD",
                    }
                },
                "required": ["target_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_conference",
            "description": "根据会议名称查询会议详情：举办时间、地点、投稿截止日期、主题等。若会议不存在会返回 error。",
            "parameters": {
                "type": "object",
                "properties": {
                    "conference_name": {
                        "type": "string",
                        "description": "会议名称，如 ICCBDA 2027、AIIoT 2027",
                    }
                },
                "required": ["conference_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_timezone",
            "description": "把某个时区的具体日期时间转换到另一个时区（自动处理夏令时）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "datetime_str": {
                        "type": "string",
                        "description": "待转换的时间，格式 YYYY-MM-DD HH:MM，例如 2027-06-19 09:00",
                    },
                    "from_timezone": {
                        "type": "string",
                        "description": "源城市名或 IANA 时区，如 东京 / Asia/Tokyo",
                    },
                    "to_timezone": {
                        "type": "string",
                        "description": "目标城市名或 IANA 时区，如 北京 / Asia/Shanghai",
                    },
                },
                "required": ["datetime_str", "from_timezone", "to_timezone"],
            },
        },
    },
]