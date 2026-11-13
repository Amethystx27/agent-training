from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from openai import OpenAI
from pydantic import ValidationError

from advanced_prompts import ADVANCED_PROMPTS
from advanced_schemas import AdvancedConferenceInfo
from validate_schema import (
    BASE_DIR,
    DATA_DIR,
    REQUEST_TIMEOUT_SECONDS,
    create_client,
    expand_selection,
    parse_json_output,
    save_raw_output,
    save_validated_output,
)


NOTICE_D_PATH = DATA_DIR / "notice_d.txt"
TEMPERATURE = 0.1


def load_notice_d() -> str:
    if not NOTICE_D_PATH.is_file():
        raise FileNotFoundError(f"找不到通知文件: {NOTICE_D_PATH.name}")
    notice = NOTICE_D_PATH.read_text(encoding="utf-8").strip()
    if not notice:
        raise ValueError("notice_d.txt 为空")
    return notice


def call_advanced_model(
    client: OpenAI,
    notice_text: str,
    prompt_version: int,
) -> str:
    model_name = os.getenv("MODEL_NAME")
    if not model_name:
        raise RuntimeError("缺少环境变量 MODEL_NAME")

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": ADVANCED_PROMPTS[prompt_version]},
            {"role": "user", "content": notice_text},
        ],
        temperature=TEMPERATURE,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("模型返回的 content 为空")
    return content


def validate_advanced_output(raw_output: str) -> dict:
    payload = parse_json_output(raw_output)
    result = AdvancedConferenceInfo.model_validate(payload)
    return result.model_dump(mode="json")


def run_job(
    client: OpenAI,
    prompt_version: int,
) -> bool:
    print(f"\n=== notice_d.txt | Advanced Prompt V{prompt_version} ===")
    try:
        raw_output = call_advanced_model(
            client,
            load_notice_d(),
            prompt_version,
        )
        print("\n--- 模型原始输出 ---")
        print(raw_output)

        raw_path = save_raw_output("d", prompt_version, raw_output)
        print(f"\n原始响应已保存: {raw_path.relative_to(BASE_DIR)}")

        validated = validate_advanced_output(raw_output)
        json_path = save_validated_output("d", prompt_version, validated)
        print("\n--- 进阶校验通过 ---")
        print(json.dumps(validated, ensure_ascii=False, indent=2))
        print(f"\nJSON 结果已保存: {json_path.relative_to(BASE_DIR)}")
        return True
    except (ValidationError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(f"\n--- 校验或调用失败 ---\n{exc}")
        return False
    except Exception as exc:
        print(f"\n--- API 请求异常 ---\n{type(exc).__name__}: {exc}")
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="实验1进阶任务：AIIoT 2027 多类别多阶段注册信息提取"
    )
    parser.add_argument(
        "--prompt-version",
        choices=["1", "2", "all"],
        default="2",
        help="选择进阶 Prompt 版本；all 表示依次运行 V1/V2",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只验证通知读取和 Prompt 选择，不调用模型 API",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="与 --dry-run 一起使用时输出完整 Prompt",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    prompt_versions = [
        int(value)
        for value in expand_selection(args.prompt_version, ("1", "2"))
    ]

    if args.dry_run:
        notice = load_notice_d()
        for prompt_version in prompt_versions:
            print(
                f"[dry-run] notice_d.txt ({len(notice)} chars), "
                f"Advanced Prompt V{prompt_version}"
            )
            if args.show_prompt:
                print(ADVANCED_PROMPTS[prompt_version])
        return 0

    try:
        client = create_client()
    except RuntimeError as exc:
        print(f"配置错误: {exc}")
        return 2

    results = [
        run_job(client, prompt_version)
        for prompt_version in prompt_versions
    ]
    failed = results.count(False)
    print(f"\n完成：成功 {len(results) - failed}，失败 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
