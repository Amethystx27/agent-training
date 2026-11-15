CITY_TZ = {
    "成都": "Asia/Shanghai", "chengdu": "Asia/Shanghai",
    "北京": "Asia/Shanghai", "beijing": "Asia/Shanghai",
    "上海": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "新加坡": "Asia/Singapore", "singapore": "Asia/Singapore",
    "东京": "Asia/Tokyo", "tokyo": "Asia/Tokyo",
    "伦敦": "Europe/London", "london": "Europe/London",
    "纽约": "America/New_York", "new york": "America/New_York",
    "洛杉矶": "America/Los_Angeles", "los angeles": "America/Los_Angeles",
}


def resolve_timezone(name: str) -> str | None:
    if not name:
        return None
    key = name.strip().lower()
    if key in CITY_TZ:
        return CITY_TZ[key]
    # 尝试直接作为 IANA 时区
    if "/" in name:
        return name
    return None