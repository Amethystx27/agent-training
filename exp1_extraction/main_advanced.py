import json
from .prompts import PROMPT_V1, PROMPT_V2
from .inputs import NOTICE_D_ADVANCED
from .extractor import extract

EXPECTED = {
    "conference_name": "AIIoT 2027",
    "start_date": "2027-06-18",
    "end_date": "2027-06-20",
    "submission_deadline": "2027-03-15",
    "location": "Chengdu, China",
}

EXPECTED_OTHER_DATES = {
    "acceptance_notification": "2027-04-20",
    "camera_ready": "2027-05-10",
    "early_bird_deadline": "2027-05-01",
}

EXPECTED_FEES = {
    ("Regular Author", "early_bird"): (400, "USD"),
    ("Regular Author", "regular"): (500, "USD"),
    ("Student Author", "early_bird"): (280, "USD"),
    ("Student Author", "regular"): (350, "USD"),
    ("Non-author Participant", "early_bird"): (200, "USD"),
    ("Non-author Participant", "regular"): (260, "USD"),
}


def score(info, ok_json: bool):
    if not ok_json or info is None:
        return 0, 0.0, 0.0, 0.0
    d = info.model_dump()
    hit = sum(1 for k, v in EXPECTED.items() if d.get(k) == v)
    key_acc = hit / len(EXPECTED)

    od_map = {x["type"]: x["date"] for x in d.get("other_dates", [])}
    od_hit = sum(1 for k, v in EXPECTED_OTHER_DATES.items() if od_map.get(k) == v)
    od_acc = od_hit / len(EXPECTED_OTHER_DATES)

    fee_map = {(f["category"], f["stage"]): (f["amount"], f["currency"])
               for f in d.get("registration_fee", [])}
    fee_hit = sum(1 for k, v in EXPECTED_FEES.items() if fee_map.get(k) == v)
    fee_acc = fee_hit / len(EXPECTED_FEES)
    return 1, key_acc, od_acc, fee_acc


def run_one(name, prompt_text):
    r = extract(prompt_text, NOTICE_D_ADVANCED, label=f"AIIoT2027 | {name}")
    json_ok, key_acc, od_acc, fee_acc = score(r["info"], r["ok"])
    return {"prompt": name, "json_ok": json_ok, "key_acc": key_acc,
            "other_dates_acc": od_acc, "fee_acc": fee_acc, "issues": r["issues"]}


def main():
    res = [run_one("V1-基础Prompt", PROMPT_V1),
           run_one("V2-优化Prompt", PROMPT_V2)]
    print("\n\n================ 对比表 ================")
    print(f"{'Prompt':<20}{'JSON合法':<10}{'关键字段':<10}{'其他日期':<10}{'费用匹配':<10}")
    for r in res:
        print(f"{r['prompt']:<20}{r['json_ok']:<10}"
              f"{r['key_acc']:<10.2f}{r['other_dates_acc']:<10.2f}{r['fee_acc']:<10.2f}")
    with open("advanced_results.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("\n结果已保存到 advanced_results.json")


if __name__ == "__main__":
    main()