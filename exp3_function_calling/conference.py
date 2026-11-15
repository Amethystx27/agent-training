import csv
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "conferences.csv")

_DEFAULT_ROWS = [
    {"name": "ICCBDA 2027", "start": "2027-05-21", "end": "2027-05-23",
     "location": "Chengdu, China", "deadline": "2027-02-15",
     "topics": "Cloud Computing;Big Data Analytics;AI;Edge Computing"},
    {"name": "AIIoT 2027", "start": "2027-06-18", "end": "2027-06-20",
     "location": "Chengdu, China", "deadline": "2027-03-15",
     "topics": "AI;IoT;Edge Computing;Federated Learning"},
    {"name": "Smart Networks 2027", "start": "2027-11-12", "end": "2027-11-13",
     "location": "Singapore", "deadline": "2027-07-24",
     "topics": "Intelligent Networking;Network Automation"},
]


def _ensure_csv():
    if os.path.exists(DB_PATH):
        return
    with open(DB_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "start", "end", "location", "deadline", "topics"])
        w.writeheader()
        for row in _DEFAULT_ROWS:
            w.writerow(row)


def load_db() -> list[dict]:
    _ensure_csv()
    rows = []
    with open(DB_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["topics"] = [t for t in r["topics"].split(";") if t]
            rows.append(r)
    return rows


def search_conference(name: str) -> dict:
    if not name or not isinstance(name, str):
        return {"error": "会议名称不能为空"}
    rows = load_db()
    target = name.strip().lower()
    for r in rows:
        if r["name"].lower() == target or target in r["name"].lower():
            return {
                "conference_name": r["name"],
                "conference_start": r["start"],
                "conference_end": r["end"],
                "location": r["location"],
                "submission_deadline": r["deadline"],
                "topics": r["topics"],
            }
    return {"error": f"Conference not found: {name}"}