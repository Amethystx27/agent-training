"""实验3：批量评估 28 题。"""
import json, re, sys, time
from pathlib import Path
from .common import DEFAULT_RESULTS_DIR, ensure_dirs
from .rag_chain import answer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = PROJECT_ROOT / "测试问题.md"


def parse_questions(path):
    items = []
    pattern = re.compile(r"^(\d+)\.\s*\[([^\]]+)\]\s*(.+)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line.strip())
        if m: items.append({"id": int(m.group(1)), "type": m.group(2), "question": m.group(3).strip()})
    return items


def main():
    ensure_dirs()
    if not QUESTIONS_PATH.exists():
        print("未找到 测试问题.md");
        return
    items = parse_questions(QUESTIONS_PATH)

    out_file = DEFAULT_RESULTS_DIR / "answers_k4.jsonl"
    with out_file.open("w", encoding="utf-8") as f:
        for item in items:
            start = time.time()
            try:
                res = answer(item["question"])
                err = None
            except Exception as e:
                res, err = None, str(e)

            record = {**item, "result": res, "error": err, "time": round(time.time() - start, 2)}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            print(f"Q{item['id']:>2} [{item['type']}] ok")
    print(f"运行完毕，结果保存在 {out_file}")


if __name__ == "__main__":
    main()