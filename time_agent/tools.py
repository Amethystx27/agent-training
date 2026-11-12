from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# ========== 会议数据库（模拟，后续可替换 AcademicOS API） ==========
CONFERENCE_DB = {
    "ICCBDA 2027": {
        "name": "ICCBDA 2027",
        "full_name": "The 11th International Conference on Cloud Computing and Big Data Analytics",
        "start_date": "2027-05-21",
        "end_date": "2027-05-23",
        "location": "Xihua University, Chengdu, China",
        "city": "Chengdu",
        "country": "China",
        "submission_deadline": "2027-02-15",
        "topics": ["Cloud Computing", "Big Data Analytics", "Artificial Intelligence",
                   "Edge Computing", "Distributed Systems"],
    },
    "AIIoT 2027": {
        "name": "AIIoT 2027",
        "full_name": "The International Conference on Artificial Intelligence and Internet of Things",
        "start_date": "2027-06-18",
        "end_date": "2027-06-20",
        "location": "Chengdu, China",
        "city": "Chengdu",
        "country": "China",
        "submission_deadline": "2027-03-15",
        "topics": ["Artificial Intelligence", "Internet of Things", "Edge Computing",
                   "Federated Learning", "Intelligent Network Systems"],
    },
    "Smart Networks 2027": {
        "name": "Smart Networks 2027",
        "full_name": "International Workshop on Smart Networks 2027",
        "start_date": "2027-11-12",
        "end_date": "2027-11-13",
        "location": "Singapore",
        "city": "Singapore",
        "country": "Singapore",
        "submission_deadline": "2027-07-24",
        "topics": ["Intelligent Networking", "Edge Computing",
                   "Network Automation", "AI-enabled Network Management"],
    },
}

# ========== 城市 → IANA 时区映射（中英文） ==========
CITY_TZ = {
    "成都": "Asia/Shanghai", "chengdu": "Asia/Shanghai",
    "北京": "Asia/Shanghai", "beijing": "Asia/Shanghai",
    "上海": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
    "新加坡": "Asia/Singapore", "singapore": "Asia/Singapore",
    "东京": "Asia/Tokyo", "tokyo": "Asia/Tokyo",
    "伦敦": "Europe/London", "london": "Europe/London",
    "纽约": "America/New_York", "new york": "America/New_York", "newyork": "America/New_York",
    "洛杉矶": "America/Los_Angeles", "los angeles": "America/Los_Angeles", "losangeles": "America/Los_Angeles",
}


def city_to_timezone(city: str):
    """城市名（中/英，大小写不敏感）→ IANA 时区。"""
    key = city.strip().lower()
    if key in CITY_TZ:
        return CITY_TZ[key]
    # 也允许用户直接传 IANA 时区名
    try:
        ZoneInfo(city)
        return city
    except ZoneInfoNotFoundError:
        return None


# ========== 工具 1：当前时间 ==========
def get_current_time(timezone: str):
    tz = city_to_timezone(timezone)
    if tz is None:
        return {"error": f"Invalid timezone or unknown city: {timezone}"}
    try:
        now = datetime.now(ZoneInfo(tz))
    except ZoneInfoNotFoundError:
        return {"error": f"Invalid timezone: {timezone}"}
    return {
        "timezone": tz,
        "datetime": now.isoformat(),
        "formatted_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "utc_offset": now.strftime("%z"),
    }


# ========== 工具 2：距今天数 ==========
def days_until(target_date: str):
    try:
        target = date.fromisoformat(target_date)
    except ValueError:
        return {"error": f"Invalid date format (expected YYYY-MM-DD): {target_date}"}
    today = date.today()
    return {
        "target_date": target_date,
        "today": today.isoformat(),
        "days_remaining": (target - today).days,
    }


# ========== 工具 3：会议查询 ==========
def search_conference(conference_name: str):
    """按名称查会议。先精确，再大小写不敏感模糊匹配。"""
    if conference_name in CONFERENCE_DB:
        return CONFERENCE_DB[conference_name]
    key = conference_name.strip().lower()
    for name, info in CONFERENCE_DB.items():
        if name.lower() == key or key in name.lower():
            return info
    return {"error": f"Conference not found: {conference_name}"}


# ========== 工具 4：时区转换（夏令时安全） ==========
def convert_timezone(datetime_str: str, from_timezone: str, to_timezone: str):
    """
    datetime_str: 'YYYY-MM-DD HH:MM' 或 ISO 格式，不带时区
    from_timezone / to_timezone: IANA 名或城市名
    """
    src = city_to_timezone(from_timezone)
    dst = city_to_timezone(to_timezone)
    if src is None:
        return {"error": f"Invalid source timezone: {from_timezone}"}
    if dst is None:
        return {"error": f"Invalid target timezone: {to_timezone}"}
    try:
        # 尝试几种常见格式
        dt = None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(datetime_str, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            dt = datetime.fromisoformat(datetime_str)
    except ValueError:
        return {"error": f"Invalid datetime: {datetime_str}"}

    aware = dt.replace(tzinfo=ZoneInfo(src))
    converted = aware.astimezone(ZoneInfo(dst))
    return {
        "input": f"{datetime_str} ({src})",
        "output": converted.strftime("%Y-%m-%d %H:%M:%S"),
        "output_timezone": dst,
        "utc_offset": converted.strftime("%z"),
    }


# 工具白名单：禁止任意执行
TOOL_REGISTRY = {
    "get_current_time": get_current_time,
    "days_until": days_until,
    "search_conference": search_conference,
    "convert_timezone": convert_timezone,
}