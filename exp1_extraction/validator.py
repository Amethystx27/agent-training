from typing import Dict, List, Tuple
from common.json_utils import parse_json_safely
from .schema import ConferenceInfo


def validate(raw: str) -> Tuple[bool, ConferenceInfo | None, List[str]]:
    issues: List[str] = []
    ok, data = parse_json_safely(raw)
    if not ok:
        return False, None, [str(data)]

    try:
        info = ConferenceInfo(**data)
    except Exception as e:
        return False, None, [f"Schema 校验失败: {e}"]

    if info.start_date and info.end_date and info.start_date > info.end_date:
        issues.append(f"start_date({info.start_date}) 晚于 end_date({info.end_date})")

    if info.submission_deadline and info.start_date and info.submission_deadline > info.start_date:
        issues.append("投稿截止日期晚于会议开始日期，疑似字段混淆")

    # 类别 × 阶段完整性（有 stage 的才算）
    stages_by_cat: Dict[str, set] = {}
    for f in info.registration_fee:
        stages_by_cat.setdefault(f.category, set()).add(f.stage)
    for c, st in stages_by_cat.items():
        if st == {"early_bird", "regular"}:
            continue
        if st == {None}:
            continue  # 基础通知允许无 stage
        issues.append(f"类别 {c} 的费用阶段不完整: {st}")

    for i, f in enumerate(info.registration_fee):
        if not f.currency or not f.currency.isalpha() or len(f.currency) != 3:
            issues.append(f"第 {i} 条费用币种可疑: {f.currency}")

    return len(issues) == 0, info, issues