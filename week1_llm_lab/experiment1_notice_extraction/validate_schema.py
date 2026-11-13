from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from prompts import PROMPTS
from schemas import ConferenceInfo


BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
RAW_OUTPUTS_DIR = OUTPUTS_DIR / "raw"
NOTICE_FILES = {
    "a": BASE_DIR / "notice_a.txt",
    "b": BASE_DIR / "notice_b.txt",
    "c": BASE_DIR / "notice_c.txt",
}
ENV_FILES = (
    BASE_DIR / ".env",
    BASE_DIR.parent / ".env",
)
TEMPERATURE = 0.1
REQUEST_TIMEOUT_SECONDS = 60


def load_environment() -> None:
    """Load the experiment-local .env first, then the legacy parent-level one."""

    for env_file in ENV_FILES:
        if env_file.is_file():
            load_dotenv(env_file)


def load_notice(notice_key: str) -> str:
    """Read one of the fixed A/B/C notices from this experiment directory."""

    path = NOTICE_FILES[notice_key]
    if not path.is_file():
        raise FileNotFoundError(f"找不到通知文件: {path.name}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"通知文件为空: {path.name}")
    return text


def create_client() -> OpenAI:
    load_environment()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少环境变量 OPENAI_API_KEY")
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def parse_json_output(raw_output: str) -> dict:
    """Parse plain JSON and tolerate a single Markdown JSON fence."""

    if not isinstance(raw_output, str) or not raw_output.strip():
        raise ValueError("模型没有返回内容")

    text = raw_output.strip()
    fenced = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("模型输出的顶层必须是 JSON 对象")
    return parsed


def validate_output(raw_output: str) -> dict:
    parsed = parse_json_output(raw_output)
    conference = ConferenceInfo.model_validate(parsed)
    return conference.model_dump(mode="json")


def output_paths(notice_key: str, prompt_version: int) -> tuple[Path, Path]:
    stem = f"notice_{notice_key}_prompt_v{prompt_version}"
    return (
        OUTPUTS_DIR / f"{stem}.json",
        RAW_OUTPUTS_DIR / f"{stem}.txt",
    )


def save_raw_output(
    notice_key: str,
    prompt_version: int,
    raw_output: str,
) -> Path:
    _, raw_path = output_paths(notice_key, prompt_version)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw_output, encoding="utf-8")
    return raw_path


def save_validated_output(
    notice_key: str,
    prompt_version: int,
    validated: dict,
) -> Path:
    json_path, _ = output_paths(notice_key, prompt_version)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(validated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return json_path


def call_model(
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
            {"role": "system", "content": PROMPTS[prompt_version]},
            {"role": "user", "content": notice_text},
        ],
        temperature=TEMPERATURE,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("模型返回的 content 为空")
    return content


def expand_selection(value: str, choices: Sequence[str]) -> list[str]:
    return list(choices) if value == "all" else [value]


def run_job(
    client: OpenAI,
    notice_key: str,
    prompt_version: int,
) -> bool:
    print(f"\n=== notice_{notice_key}.txt | Prompt V{prompt_version} ===")
    try:
        notice_text = load_notice(notice_key)
        raw_output = call_model(client, notice_text, prompt_version)
        print("\n--- 模型原始输出 ---")
        print(raw_output)
        raw_path = save_raw_output(notice_key, prompt_version, raw_output)
        print(f"\n原始响应已保存: {raw_path.relative_to(BASE_DIR)}")

        validated = validate_output(raw_output)
        json_path = save_validated_output(
            notice_key,
            prompt_version,
            validated,
        )
        print("\n--- 校验通过 ---")
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
        description="实验1：统一会议通知信息提取与严格校验入口"
    )
    parser.add_argument(
        "--notice",
        choices=["a", "b", "c", "all"],
        default="a",
        help="选择固定通知文件；all 表示依次运行 A/B/C",
    )
    parser.add_argument(
        "--prompt-version",
        choices=["1", "2", "all"],
        default="2",
        help="选择 Prompt 版本；all 表示依次运行 V1/V2",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只验证文件读取和 Prompt 选择，不调用模型 API",
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="与 --dry-run 一起使用时输出完整 Prompt",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    notice_keys = expand_selection(args.notice, tuple(NOTICE_FILES))
    prompt_versions = [
        int(value)
        for value in expand_selection(args.prompt_version, ("1", "2"))
    ]

    if args.dry_run:
        for notice_key in notice_keys:
            notice_text = load_notice(notice_key)
            for prompt_version in prompt_versions:
                print(
                    f"[dry-run] notice_{notice_key}.txt "
                    f"({len(notice_text)} chars), Prompt V{prompt_version}"
                )
                if args.show_prompt:
                    print(PROMPTS[prompt_version])
        return 0

    try:
        client = create_client()
    except RuntimeError as exc:
        print(f"配置错误: {exc}")
        return 2

    results = [
        run_job(client, notice_key, prompt_version)
        for notice_key in notice_keys
        for prompt_version in prompt_versions
    ]
    failed = results.count(False)
    print(f"\n完成：成功 {len(results) - failed}，失败 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
