from agent import run_agent
from logger import ToolCallLogger

QUESTIONS = [
    ("Q1", "ICCBDA 2027 的投稿截止日期是什么时候？距离今天还有多少天？"),
    ("Q2", "AIIoT 2027 在哪里举办？距离会议开始还有多少天？"),
    ("Q3", "现在新加坡和纽约分别是几点？"),
    ("Q4", "东京明天上午9点对应北京时间几点？"),
    ("Q5", "What is the submission deadline of ICCBDA 2027? How many days are left?"),
    ("Q6", "帮我查询一个不存在的会议 XYZ 2027 的投稿截止日期。"),
]

if __name__ == "__main__":
    logger = ToolCallLogger()
    for tag, q in QUESTIONS:
        print(f"\n{'=' * 72}\n{tag}: {q}\n{'=' * 72}")
        answer = run_agent(q, logger)
        print("---- 最终回答 ----")
        print(answer)
        logger.dump()