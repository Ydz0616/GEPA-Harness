#!/home/ubuntu/repos/Hidden-Layer-Internal/.venv/bin/python
"""Capture raw Composio CallToolResult values for recorded GitHub calls."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from hidden_layer.config import Settings
from hidden_layer import db
from hidden_layer.tools import composio

BASE = Path("/home/ubuntu/improve-runs/ghshim")
TOOLS_PATH = Path("/home/ubuntu/improve-runs/probe/composio_tools.json")
PAIRS_PATH = Path("/home/ubuntu/improve-runs/probe/recorded_pairs.json")
RAW_PATH = BASE / "composio_raw.jsonl"
ERROR_PATH = BASE / "composio_capture_errors.jsonl"
CONCURRENCY = 4
SAMPLE_LIMIT = 20
RANDOM_SEED = 20261021


def canonical_args(args: dict[str, Any]) -> str:
    return json.dumps(args, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def read_inputs(input_path: Path = PAIRS_PATH) -> tuple[
    list[str], dict[str, list[dict[str, Any]]], dict[str, int], Counter[str]
]:
    tool_definitions = json.loads(TOOLS_PATH.read_text())
    tool_names = [tool["name"] for tool in tool_definitions]
    read_only_names = {
        tool["name"]
        for tool in tool_definitions
        if tool.get("annotations", {}).get("read_only_hint") is True
    }
    by_tool: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    skipped: Counter[str] = Counter()

    for pair in json.loads(input_path.read_text()):
        name = pair.get("name")
        if name not in tool_names:
            skipped["unknown_tool"] += 1
            continue
        if name not in read_only_names:
            skipped["non_read_only_tool"] += 1
            continue
        raw_args = pair.get("args")
        try:
            args = (
                json.loads(raw_args or "{}")
                if isinstance(raw_args, str)
                else raw_args
            )
        except json.JSONDecodeError:
            skipped[
                "truncated_args" if isinstance(raw_args, str) and len(raw_args) == 60
                else "invalid_args"
            ] += 1
            continue
        if not isinstance(args, dict):
            skipped["invalid_args"] += 1
            continue
        by_tool[name].setdefault(canonical_args(args), args)

    rng = random.Random(RANDOM_SEED)
    selected: dict[str, list[dict[str, Any]]] = {}
    unique_counts: dict[str, int] = {}
    for name in tool_names:
        unique_args = list(by_tool[name].values())
        unique_counts[name] = len(unique_args)
        selected[name] = (
            rng.sample(unique_args, SAMPLE_LIMIT)
            if len(unique_args) > SAMPLE_LIMIT
            else unique_args
        )
    return tool_names, selected, unique_counts, skipped


def captured_keys() -> set[tuple[str, str]]:
    existing: set[tuple[str, str]] = set()
    if not RAW_PATH.exists():
        return existing
    with RAW_PATH.open(encoding="utf-8") as source:
        for line in source:
            try:
                record = json.loads(line)
                args = record["args"]
                if "call_result" in record and isinstance(args, dict):
                    existing.add((record["name"], canonical_args(args)))
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
    return existing


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as descriptor:
        descriptor.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        descriptor.flush()


def is_timeout_exception(exc: Exception) -> bool:
    kind = type(exc).__name__.lower()
    message = str(exc).lower()
    return (
        isinstance(exc, (TimeoutError, asyncio.TimeoutError))
        or "timeout" in kind
        or "timed out" in message
        or "timeout" in message
    )


def is_timeout_result(result: Any) -> bool:
    if not getattr(result, "is_error", False):
        return False
    text = "\n".join(
        content.text for content in getattr(result, "content", [])
        if getattr(content, "type", None) == "text"
    ).lower()
    return "timed out" in text or "timeout" in text


async def capture_all(
    probe_content_control: bool = False, input_path: Path = PAIRS_PATH
) -> None:
    tool_names, selected, unique_counts, skipped = read_inputs(input_path)
    already_captured = captured_keys()
    pending = [
        (name, args, False)
        for name in tool_names
        for args in selected[name]
        if (name, canonical_args(args)) not in already_captured
    ]
    captured_by_tool: Counter[str] = Counter()
    failed_by_tool: Counter[str] = Counter()
    control_captured = 0
    control_failed = 0
    if probe_content_control:
        control_args = {
            "owner": "sanic-org",
            "repo": "sanic",
            "path": "README.rst",
        }
        control_key = (
            "GITHUB_GET_REPOSITORY_CONTENT", canonical_args(control_args)
        )
        if control_key not in already_captured:
            pending.append(("GITHUB_GET_REPOSITORY_CONTENT", control_args, True))
    concurrency = asyncio.Semaphore(CONCURRENCY)
    file_lock = asyncio.Lock()
    settings = Settings()
    if settings.tenant_id != "devinlive":
        raise RuntimeError("Refusing capture: HL_TENANT_ID must be devinlive")

    pool = db.pg_pool(settings, min_size=1, max_size=1)
    try:
        url = composio.resolve_mcp_url(pool)
    finally:
        pool.close()
    if not url:
        raise RuntimeError("No enabled Composio MCP URL is registered")

    server = composio.make_mcp_server(
        url,
        settings.composio_api_key,
        toolkit=composio.GITHUB_TOOLKIT,
        timeout_s=180,
        full_surface=True,
    )

    async with server:

        async def capture_one(
            name: str, args: dict[str, Any], is_probe_control: bool
        ) -> None:
            nonlocal control_captured, control_failed
            attempts: list[float] = []
            async with concurrency:
                for attempt in range(1, 3):
                    started = time.monotonic()
                    try:
                        result = await server.session.call_tool(name, args)
                    except Exception as exc:
                        attempts.append(time.monotonic() - started)
                        if attempt == 1 and is_timeout_exception(exc):
                            print(f"timeout retry tool={name}", flush=True)
                            continue
                        error = {
                            "name": name,
                            "args": args,
                            "source": "probe_control" if is_probe_control else "recorded_pairs",
                            "attempts": attempt,
                            "attempt_latencies_s": attempts,
                            "error_type": type(exc).__name__,
                            "error": str(exc).replace(
                                settings.composio_api_key, "[REDACTED]"
                            )[:1000] if settings.composio_api_key else str(exc)[:1000],
                        }
                        async with file_lock:
                            append_jsonl(ERROR_PATH, error)
                        if is_probe_control:
                            control_failed += 1
                        else:
                            failed_by_tool[name] += 1
                        print(
                            f"failed tool={name} attempt={attempt} "
                            f"latency_s={sum(attempts):.1f} error={type(exc).__name__}",
                            flush=True,
                        )
                        return

                    attempts.append(time.monotonic() - started)
                    if attempt == 1 and is_timeout_result(result):
                        print(f"timeout-result retry tool={name}", flush=True)
                        continue

                    record = {
                        "name": name,
                        "args": args,
                        "latency_s": sum(attempts),
                        "attempt_latencies_s": attempts,
                        "attempts": attempt,
                        "call_result": result.model_dump(
                            mode="json", by_alias=True, exclude_none=False
                        ),
                    }
                    if is_probe_control:
                        record["source"] = "probe_control"
                    async with file_lock:
                        append_jsonl(RAW_PATH, record)
                    if is_probe_control:
                        control_captured += 1
                    else:
                        captured_by_tool[name] += 1
                    print(
                        f"captured tool={name} attempt={attempt} "
                        f"latency_s={sum(attempts):.1f}",
                        flush=True,
                    )
                    return

        await asyncio.gather(
            *(capture_one(name, args, is_control) for name, args, is_control in pending)
        )

    print("\nCapture summary")
    print("| Tool | unique args | selected | already captured | new results | failures |")
    print("|---|---:|---:|---:|---:|---:|")
    for name in tool_names:
        selected_keys = {(name, canonical_args(args)) for args in selected[name]}
        already = len(selected_keys & already_captured)
        print(
            f"| {name} | {unique_counts[name]} | {len(selected[name])} | {already} | "
            f"{captured_by_tool[name]} | {failed_by_tool[name]} |"
        )
    print(
        f"new results: {sum(captured_by_tool.values())}; "
        f"failures: {sum(failed_by_tool.values())}"
    )
    if probe_content_control:
        print(
            f"probe content control: captured={control_captured} "
            f"failures={control_failed}"
        )
    print(f"skipped: {json.dumps(dict(sorted(skipped.items())), sort_keys=True)}")
    print(f"raw output: {RAW_PATH}")
    print(f"errors: {ERROR_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-file",
        type=Path,
        default=PAIRS_PATH,
        help="JSON call list to capture",
    )
    parser.add_argument(
        "--probe-content-control",
        action="store_true",
        help="capture the same read-only README call used by composio_probe.py",
    )
    arguments = parser.parse_args()
    asyncio.run(capture_all(arguments.probe_content_control, arguments.input_file))
