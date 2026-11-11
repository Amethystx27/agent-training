"""
实验1：不同 Prompt 版本对比（生成对比表 + 结果文件）
=====================================================
对两个样本会议通知，分别用 Prompt V1（基础版）和 V2（改进版）调用模型，
解析并校验后，统计各版本在「JSON 合法性 / 字段完整率 / 日期格式 / 多类别费用捕获」
上的表现，输出 Markdown 对比表与 results.json。

运行:  python compare_prompts.py
前置:  .env 已配置；pip install -r requirements.txt
"""

import json
import statistics
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

import main as exp1  # 复用主程序的模型调用与校验逻辑

SAMPLES = {
    "单类别费用样例": Path(__file__).resolve().parent / "sample_meeting_notice.txt",
    "多类别费用样例": Path(__file__).resolve().parent / "sample_meeting_notice_multi.txt",
    "缺失信息样例": Path(__file__).resolve().parent / "sample_meeting_notice_hard.txt",
}

FIELDS = [
    "conference_name", "date", "location", "theme",
    "submission_deadline", "registration_fees",
]


def evaluate(prompt_version: int, sample_path: Path) -> dict:
    notice = sample_path.read_text(encoding="utf-8")
    try:
        raw = exp1.call_llm(notice, prompt_version=prompt_version)
        result = exp1.parse_and_validate(raw)  # 通过说明 JSON 合法 + 字段/类型/日期校验通过
        valid = True
        err = ""
    except Exception as e:
        result = {}
        valid = False
        err = str(e)[:120]

    filled = sum(1 for f in FIELDS if result.get(f) not in (None, [], ""))
    fees = result.get("registration_fees") or []
    multi = len(fees)
    return {
        "prompt_version": prompt_version,
        "sample": sample_path.stem,
        "json_valid": valid,
        "field_completeness": filled / len(FIELDS),
        "fee_categories_captured": multi,
        "error": err,
        "result": result,
    }


def main() -> None:
    rows = []
    for pv in (1, 2):
        for name, path in SAMPLES.items():
            rows.append(evaluate(pv, path))

    # ---- 输出 Markdown 对比表 ----
    print("\n# 不同 Prompt 实验结果对比表\n")
    print("| 样本 | Prompt版本 | JSON合法 | 字段完整率 | 捕获费用档位数 | 错误信息 |")
    print("|------|-----------|----------|------------|----------------|----------|")
    for r in rows:
        print(
            f"| {r['sample']} | V{r['prompt_version']} "
            f"| {'✅' if r['json_valid'] else '❌'} "
            f"| {r['field_completeness']*100:.0f}% "
            f"| {r['fee_categories_captured']} "
            f"| {r['error'] or '—'} |"
        )

    # ---- 汇总：两版本整体指标 ----
    print("\n## 汇总\n")
    for pv in (1, 2):
        sub = [r for r in rows if r["prompt_version"] == pv]
        print(
            f"- **Prompt V{pv}**：JSON 合法率 "
            f"{statistics.mean(int(r['json_valid']) for r in sub)*100:.0f}%，"
            f"平均字段完整率 "
            f"{statistics.mean(r['field_completeness'] for r in sub)*100:.0f}%，"
            f"平均捕获费用档位数 "
            f"{statistics.mean(r['fee_categories_captured'] for r in sub):.1f}"
        )

    # ---- 保存原始结果，供实验报告引用 ----
    out = Path(__file__).resolve().parent / "results.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n原始结果已保存至: {out}")


if __name__ == "__main__":
    main()
