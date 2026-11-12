import re
from datetime import datetime
from typing import Any, Optional

REQUIRED_FIELDS = [
    "conference_name", "conference_full_name", "start_date", "end_date",
    "location", "topics", "submission_deadline", "other_dates",
    "registration_fee", "organizer",
]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALLOWED_OTHER_TYPES = {
    "abstract_registration", "acceptance_notification",
    "camera_ready", "early_bird_registration",
}


def _valid_date(s: Any) -> bool:
    if s is None:
        return True
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate(payload: dict) -> tuple[bool, list[str]]:
    """返回 (是否通过, 错误列表)。"""
    errors: list[str] = []

    # 1) 必需字段全部出现
    for f in REQUIRED_FIELDS:
        if f not in payload:
            errors.append(f"缺少字段: {f}")

    # 2) 字符串 / null 字段
    for f in ["conference_name", "conference_full_name", "location", "organizer"]:
        v = payload.get(f)
        if v is not None and not isinstance(v, str):
            errors.append(f"{f} 类型应为 string/null，实际 {type(v).__name__}")

    # 3) 日期字段
    for f in ["start_date", "end_date", "submission_deadline"]:
        if not _valid_date(payload.get(f)):
            errors.append(f"{f} 日期格式非法（应为 YYYY-MM-DD 或 null）: {payload.get(f)!r}")

    if payload.get("start_date") and payload.get("end_date"):
        if payload["start_date"] > payload["end_date"]:
            errors.append("start_date 晚于 end_date")

    # 4) topics 必须是数组，元素为字符串
    topics = payload.get("topics")
    if not isinstance(topics, list) or not all(isinstance(t, str) for t in topics):
        errors.append("topics 必须是字符串数组")

    # 5) other_dates
    od = payload.get("other_dates")
    if od is not None:
        if not isinstance(od, list):
            errors.append("other_dates 必须是数组")
        else:
            for i, item in enumerate(od):
                if not isinstance(item, dict) or "type" not in item or "date" not in item:
                    errors.append(f"other_dates[{i}] 缺少 type/date")
                    continue
                if item["type"] not in ALLOWED_OTHER_TYPES:
                    errors.append(f"other_dates[{i}].type 非法: {item['type']}")
                if not _valid_date(item["date"]):
                    errors.append(f"other_dates[{i}].date 非法: {item['date']!r}")

    # 6) registration_fee
    fees = payload.get("registration_fee")
    if fees is not None:
        if not isinstance(fees, list):
            errors.append("registration_fee 应为数组或 null")
        else:
            for i, item in enumerate(fees):
                if not isinstance(item, dict):
                    errors.append(f"registration_fee[{i}] 应为对象")
                    continue
                for k in ("category", "amount", "currency"):
                    if k not in item:
                        errors.append(f"registration_fee[{i}] 缺少 {k}")
                amt = item.get("amount")
                if not isinstance(amt, (int, float)) or isinstance(amt, bool):
                    errors.append(f"registration_fee[{i}].amount 必须为数值: {amt!r}")
                cur = item.get("currency")
                if not isinstance(cur, str) or len(cur) == 0:
                    errors.append(f"registration_fee[{i}].currency 必须为非空字符串")
                # 两阶段费用
                if "stage" in item and item["stage"] not in ("early_bird", "regular"):
                    errors.append(f"registration_fee[{i}].stage 非法: {item['stage']!r}")
                if "deadline" in item and not _valid_date(item["deadline"]):
                    errors.append(f"registration_fee[{i}].deadline 非法: {item['deadline']!r}")

    return len(errors) == 0, errors


def check_aiiot_completeness(payload: dict) -> list[str]:
    """针对 AIIoT 进阶挑战的专项一致性校验。"""
    problems: list[str] = []
    fees = payload.get("registration_fee") or []

    # 每个类别 × 每个阶段都应出现
    expected = {
        ("Regular Author", "early_bird"), ("Regular Author", "regular"),
        ("Student Author", "early_bird"), ("Student Author", "regular"),
        ("Non-author Participant", "early_bird"), ("Non-author Participant", "regular"),
    }
    actual = {(f.get("category"), f.get("stage")) for f in fees}
    missing = expected - actual
    if missing:
        problems.append(f"注册费用组合缺失: {sorted(missing)}")

    # 早鸟价必须低于普通价
    by_cat: dict[str, dict[str, float]] = {}
    for f in fees:
        by_cat.setdefault(f.get("category"), {})[f.get("stage")] = f.get("amount")
    for cat, stages in by_cat.items():
        e, r = stages.get("early_bird"), stages.get("regular")
        if isinstance(e, (int, float)) and isinstance(r, (int, float)) and e >= r:
            problems.append(f"{cat} 早鸟价({e})未低于普通价({r})")

    # 币种统一
    currencies = {f.get("currency") for f in fees if f.get("currency")}
    if len(currencies) > 1:
        problems.append(f"注册费用币种不一致: {currencies}")

    return problems