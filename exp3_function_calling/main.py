import json
from .agent import run_agent

TEST_QUESTIONS = [
    ("Q1", "ICCBDA 2027 的投稿截止日期是什么时候？距离今天还有多少天？"),
    ("Q2", "AIIoT 2027 在哪里举办？距离会议开始还有多少天？"),
    ("Q3", "现在新加坡和纽约分别是几点？"),
    ("Q4", "东京明天上午9点对应北京时间几点？"),
    ("Q5", "What is the submission deadline of ICCBDA 2027? How many days are left?"),
    ("Q6", "帮我查询一个不存在的会议 XYZ 2027 的投稿截止日期。"),
]


def main():
    all_logs = []
    for qid, q in TEST_QUESTIONS:
        print(f"\n{'='*70}\n{qid}: {q}\n{'='*70}")
        r = run_agent(q)
        all_logs.append({"id": qid, "question": q, "answer": r["answer"], "log": r["log"]})

    with open("agent_logs.json", "w", encoding="utf-8") as f:
        json.dump(all_logs, f, ensure_ascii=False, indent=2)
    print("\n所有调用日志已保存到 agent_logs.json")


if __name__ == "__main__":
    main()