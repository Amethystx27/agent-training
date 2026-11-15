from datetime import datetime, date
from zoneinfo import ZoneInfo
from .conference_db import search_conference as _search_conference
from .city_timezone import resolve_timezone


def get_current_time(timezone: str) -> dict:
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        return {"error": f"无效时区: {timezone}"}
    now = datetime.now(tz)
    return {
        "timezone": timezone,
        "datetime": now.isoformat(),
        "formatted_time": now.strftime("%Y-%m-%d %H:%M:%S"),
    }


def days_until(target_date: str) -> dict:
    try:
        target = date.fromisoformat(target_date)
    except Exception:
        return {"error": f"无效日期: {target_date}，应为 YYYY-MM-DD"}
    today = date.today()
    return {
        "target_date": target_date,
        "today": today.isoformat(),
        "days_remaining": (target - today).days,
    }


def get_conference_deadline(conference_name: str) -> dict:
    return _search_conference(conference_name)


def search_conference(conference_name: str) -> dict:
    return _search_conference(conference_name)


def convert_timezone(datetime_str: str, from_tz: str, to_tz: str) -> dict:
    """datetime_str: ISO 格式（如 2027-05-01T09:00:00）"""
    try:
        src = ZoneInfo(from_tz)
        dst = ZoneInfo(to_tz)
    except Exception as e:
        return {"error": f"无效时区: {e}"}
    try:
        dt = datetime.fromisoformat(datetime_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=src)
        converted = dt.astimezone(dst)
        return {
            "original": {"datetime": dt.isoformat(), "timezone": from_tz},
            "converted": {"datetime": converted.isoformat(), "timezone": to_tz,
                          "formatted": converted.strftime("%Y-%m-%d %H:%M:%S")},
        }
    except Exception as e:
        return {"error": f"时间转换失败: {e}"}


def get_timezone_for_city(city: str) -> dict:
    tz = resolve_timezone(city)
    if tz is None:
        return {"error": f"无法识别的城市: {city}"}
    return {"city": city, "timezone": tz}


# 白名单：只允许通过注册表调用
TOOL_REGISTRY = {
    "get_current_time": get_current_time,
    "days_until": days_until,
    "get_conference_deadline": get_conference_deadline,
    "search_conference": search_conference,
    "convert_timezone": convert_timezone,
    "get_timezone_for_city": get_timezone_for_city,
}