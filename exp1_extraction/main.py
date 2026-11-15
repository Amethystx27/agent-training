from .prompts import PROMPT_V1
from .inputs import NOTICE_A, NOTICE_B, NOTICE_C
from .extractor import extract


def main():
    cases = [
        ("通知A-完整通知", NOTICE_A),
        ("通知B-信息不完整", NOTICE_B),
        ("通知C-多日期易混淆", NOTICE_C),
    ]
    results = []
    for label, text in cases:
        results.append(extract(PROMPT_V1, text, label=label))

    print("\n\n==== 汇总 ====")
    for r in results:
        print(f"{r['label']}: {'通过' if r['ok'] else '未通过'}"
              + ("" if r['ok'] else f" | {r['issues']}"))


if __name__ == "__main__":
    main()