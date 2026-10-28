#!/home/ubuntu/repos/Hidden-Layer-Internal/.venv/bin/python
"""Compare the local shim's full MCP results with raw Composio captures."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import httpx2, streamable_http_client
from mcp.types import Tool

ROOT = Path("/home/ubuntu/improve-runs/ghshim")
TOOLS_PATH = Path("/home/ubuntu/improve-runs/probe/composio_tools.json")
RAW_PATH = ROOT / "composio_raw.jsonl"
REPORT_PATH = ROOT / "replay_report.json"
SERVER_URL = "http://127.0.0.1:8765/mcp?user_id=devinlive"
GITHUB_API = "https://api.github.com"
VOLATILE_FIELDS = {
    "created_at", "updated_at", "pushed_at", "stargazers_count", "watchers_count",
    "forks_count", "open_issues_count", "score", "incomplete_results", "total_count",
    "rate_limit", "rateLimit", "current_user_can_push",
}
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def read_github_token() -> str:
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        token = result.stdout.strip()
        if token:
            return token
    except (OSError, subprocess.SubprocessError):
        pass
    return os.environ.get("GITHUB_SHIM_TOKEN", "").strip()


def canonical_args(args: dict[str, Any]) -> str:
    return json.dumps(args, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def load_records() -> tuple[list[str], dict[str, list[dict[str, Any]]], Counter[str]]:
    tool_names = [tool["name"] for tool in json.loads(TOOLS_PATH.read_text())]
    known_names = set(tool_names)
    records: dict[str, list[dict[str, Any]]] = {name: [] for name in tool_names}
    seen: set[tuple[str, str]] = set()
    skipped: Counter[str] = Counter()
    if not RAW_PATH.exists():
        return tool_names, records, Counter({"raw_file_missing": 1})

    with RAW_PATH.open(encoding="utf-8") as source:
        for line in source:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                skipped["invalid_jsonl"] += 1
                continue
            name = record.get("name")
            args = record.get("args")
            if name not in known_names:
                skipped["tool_not_in_snapshot"] += 1
                continue
            if not isinstance(args, dict) or not isinstance(record.get("call_result"), dict):
                skipped["invalid_capture_record"] += 1
                continue
            key = (name, canonical_args(args))
            if key in seen:
                skipped["duplicate_capture"] += 1
                continue
            seen.add(key)
            records[name].append(record)
    return tool_names, records, skipped


async def read_rate_limits(token: str) -> dict[str, Any]:
    current_token = await asyncio.to_thread(read_github_token)
    token = current_token or token
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            response = await client.get(f"{GITHUB_API}/rate_limit", headers=headers)
            if response.status_code == 401:
                current_token = await asyncio.to_thread(read_github_token)
                if current_token:
                    headers["Authorization"] = f"token {current_token}"
                    response = await client.get(
                        f"{GITHUB_API}/rate_limit", headers=headers
                    )
        if response.is_error:
            return {"http_status": response.status_code}
        resources = response.json().get("resources", {})
        return {
            name: resources.get(name)
            for name in ("core", "search", "code_search")
            if resources.get(name) is not None
        }
    except (httpx.HTTPError, ValueError):
        return {"status": "unavailable"}


async def wait_for_code_search_quota(token: str) -> dict[str, Any]:
    while True:
        limits = await read_rate_limits(token)
        resource = limits.get("code_search") or limits.get("search")
        if not isinstance(resource, dict):
            raise RuntimeError("Could not read the GitHub code_search rate limit")
        if int(resource.get("remaining", 0)) > 0:
            return limits
        reset = float(resource.get("reset", time.time() + 60))
        await asyncio.sleep(max(1.0, min(reset - time.time() + 1, 60.0)))


def normalize_result_shape(value: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(value, ensure_ascii=False))
    for content in normalized.get("content", []):
        if content.get("type") != "text" or not isinstance(content.get("text"), str):
            continue
        try:
            content["text"] = json.loads(content["text"])
        except json.JSONDecodeError:
            continue
    return normalized


def diff_paths(expected: Any, actual: Any, path: str = "$") -> list[str]:
    if type(expected) is not type(actual):
        return [path]
    if isinstance(expected, dict):
        paths: list[str] = []
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}"
            if key not in expected or key not in actual:
                paths.append(child)
            else:
                paths.extend(diff_paths(expected[key], actual[key], child))
        return paths
    if isinstance(expected, list):
        paths = []
        if len(expected) != len(actual):
            paths.append(f"{path}.length")
        for index, (left, right) in enumerate(zip(expected, actual)):
            paths.extend(diff_paths(left, right, f"{path}[{index}]"))
        return paths
    return [] if expected == actual else [path]


def envelope_from_result(result: dict[str, Any]) -> dict[str, Any] | None:
    for content in result.get("content", []):
        if content.get("type") != "text":
            continue
        try:
            envelope = json.loads(content["text"])
        except (KeyError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(envelope, dict):
            return envelope
    return None


def is_rate_limit_error(result: dict[str, Any]) -> bool:
    envelope = envelope_from_result(result)
    if not envelope or envelope.get("mercury_last_http_status_code") != 403:
        return False
    error = envelope.get("error")
    data = envelope.get("data")
    message = data.get("message", "") if isinstance(data, dict) else ""
    return "rate limit" in f"{error} {message}".lower()


def differs_are_drift(
    name: str,
    args: dict[str, Any],
    paths: list[str],
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> bool:
    if not paths:
        return False
    if all(path.endswith((".log_id", ".logId")) for path in paths):
        return True
    if name == "GITHUB_SEARCH_CODE" and is_rate_limit_error(expected):
        actual_envelope = envelope_from_result(actual)
        if actual_envelope and actual_envelope.get("successful") is True:
            return True
    if name.startswith(("GITHUB_SEARCH_", "GITHUB_FIND_PULL_REQUESTS")):
        return all(
            ".data.items" in path
            or any(f".{field}" in path for field in VOLATILE_FIELDS)
            or path.endswith((".log_id", ".logId"))
            for path in paths
        )
    if any(any(f".{field}" in path for field in VOLATILE_FIELDS) for path in paths):
        return True
    if name == "GITHUB_GET_REPOSITORY_CONTENT":
        return not SHA_RE.fullmatch(str(args.get("ref", ""))) and all(
            path.startswith("$.content[0].text.data")
            or path.endswith((".log_id", ".logId"))
            for path in paths
        )
    if name == "GITHUB_GET_A_COMMIT":
        return not SHA_RE.fullmatch(str(args.get("ref", ""))) and all(
            path.startswith("$.content[0].text.data")
            or path.endswith((".log_id", ".logId"))
            for path in paths
        )
    if name == "GITHUB_LIST_COMMITS":
        return not SHA_RE.fullmatch(str(args.get("sha", ""))) and all(
            path.startswith("$.content[0].text.data")
            or path.endswith((".log_id", ".logId"))
            for path in paths
        )
    return False


async def run(
    anonymous_pinned_content: bool, only_tool: str | None = None
) -> dict[str, Any]:
    tool_names, records, skipped = load_records()
    if only_tool is not None and only_tool not in records:
        raise ValueError(f"Unknown tool in snapshot: {only_tool}")
    previous_tools: dict[str, Any] = {}
    if only_tool is not None and REPORT_PATH.exists():
        try:
            previous_tools = json.loads(REPORT_PATH.read_text()).get("tools", {})
        except (OSError, json.JSONDecodeError):
            previous_tools = {}
    token = await asyncio.to_thread(read_github_token)
    has_token = bool(token)
    mode = "authenticated" if has_token else "blocked-no-token"
    if not has_token and anonymous_pinned_content:
        mode = "anonymous-pinned-content"

    rate_limits = await read_rate_limits(token)
    selected = {name: list(records[name]) for name in tool_names}
    if only_tool is not None:
        selected = {
            name: list(records[name]) if name == only_tool else []
            for name in tool_names
        }
    if not has_token:
        selected = {name: [] for name in tool_names}
        if anonymous_pinned_content:
            quota = rate_limits.get("core", {})
            remaining = quota.get("remaining", 0) if isinstance(quota, dict) else 0
            candidates = [
                record for record in records.get("GITHUB_GET_REPOSITORY_CONTENT", [])
                if SHA_RE.fullmatch(str(record["args"].get("ref", "")))
            ]
            for record in candidates[:min(3, max(0, int(remaining)))]:
                selected["GITHUB_GET_REPOSITORY_CONTENT"].append(record)
            if not candidates:
                skipped["no_pinned_content_references"] += 1
        else:
            skipped["replay_requires_token"] += sum(
                len(tool_records) for tool_records in records.values()
            )

    report: dict[str, Any] = {
        "server_url": SERVER_URL,
        "reference": str(RAW_PATH),
        "comparison": "full CallToolResult; JSON text bodies are parsed for JSON-equality",
        "reference_record_counts": dict(Counter(
            record.get("source", "recorded_pairs")
            for tool_records in records.values()
            for record in tool_records
        )),
        "selection": only_tool or "all",
        "mode": mode,
        "token_available_via_gh_cli_or_environment": has_token,
        "rate_limits_before_replay": rate_limits,
        "skipped_record_counts": dict(sorted(skipped.items())),
        "tool_list_match": None,
        "mismatched_tool_schemas": [],
        "remote_tool_count": 0,
        "tools": previous_tools,
    }

    if not any(selected.values()):
        report["tools"] = {
            name: {
                "n": 0,
                "exact": 0,
                "json_equal": 0,
                "differs": 0,
                "drift": 0,
                "mismatch": 0,
                "call_errors": 0,
                "top_differing_paths": [],
            }
            for name in tool_names
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        return report

    headers = {"x-api-key": "local-shim-replay"}
    async with httpx2.AsyncClient(
        headers=headers, timeout=httpx2.Timeout(25.0), follow_redirects=False
    ) as http_client:
        async with streamable_http_client(SERVER_URL, http_client=http_client) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                remote_tools = await session.list_tools()
                remote_by_name = {tool.name: tool for tool in remote_tools.tools}
                expected_raw = json.loads(TOOLS_PATH.read_text())
                expected_by_name = {
                    tool["name"]: Tool.model_validate(tool).model_dump(
                        by_alias=True, exclude_none=True, mode="json"
                    )
                    for tool in expected_raw
                }
                remote_payloads = {
                    name: tool.model_dump(by_alias=True, exclude_none=True, mode="json")
                    for name, tool in remote_by_name.items()
                }
                mismatched_tool_schemas = [
                    name for name, expected in expected_by_name.items()
                    if remote_payloads.get(name) != expected
                ]
                report["tool_list_match"] = (
                    len(remote_by_name) == len(tool_names)
                    and set(remote_by_name) == set(tool_names)
                    and not mismatched_tool_schemas
                )
                report["mismatched_tool_schemas"] = mismatched_tool_schemas
                report["remote_tool_count"] = len(remote_tools.tools)

                for name in tool_names:
                    if only_tool is not None and name != only_tool:
                        if name not in report["tools"]:
                            report["tools"][name] = {
                                "n": 0,
                                "exact": 0,
                                "json_equal": 0,
                                "differs": 0,
                                "drift": 0,
                                "mismatch": 0,
                                "call_errors": 0,
                                "top_differing_paths": [],
                            }
                        continue
                    tool_records = selected[name]
                    row = {
                        "n": len(tool_records),
                        "exact": 0,
                        "json_equal": 0,
                        "differs": 0,
                        "drift": 0,
                        "mismatch": 0,
                        "call_errors": 0,
                        "top_differing_paths": [],
                    }
                    path_counts: Counter[str] = Counter()
                    for record in tool_records:
                        if name == "GITHUB_SEARCH_CODE":
                            await wait_for_code_search_quota(token)
                        try:
                            response = await session.call_tool(name, record["args"])
                        except Exception as exc:
                            row["call_errors"] += 1
                            path_counts[f"transport.{type(exc).__name__}"] += 1
                            continue
                        actual = response.model_dump(
                            mode="json", by_alias=True, exclude_none=False
                        )
                        expected = record["call_result"]
                        if actual == expected:
                            row["exact"] += 1
                            continue
                        expected_normalized = normalize_result_shape(expected)
                        actual_normalized = normalize_result_shape(actual)
                        if expected_normalized == actual_normalized:
                            row["json_equal"] += 1
                            continue
                        paths = diff_paths(expected_normalized, actual_normalized)
                        row["differs"] += 1
                        is_drift = differs_are_drift(
                            name, record["args"], paths, expected, actual
                        )
                        row["drift" if is_drift else "mismatch"] += 1
                        path_counts.update(paths)

                    row["top_differing_paths"] = [
                        {"path": path, "count": count}
                        for path, count in path_counts.most_common(10)
                    ]
                    report["tools"][name] = row

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def print_table(report: dict[str, Any]) -> None:
    print("| Tool | n | exact | JSON-equal | differs | drift | mismatch | call errors | Top differing paths |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for name, row in report["tools"].items():
        paths = ", ".join(item["path"] for item in row["top_differing_paths"]) or "—"
        print(
            f"| {name} | {row['n']} | {row['exact']} | {row['json_equal']} | "
            f"{row['differs']} | {row['drift']} | {row['mismatch']} | "
            f"{row['call_errors']} | {paths} |"
        )
    print(f"\nReport: {REPORT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--anonymous-pinned-content",
        action="store_true",
        help="if no token is available, replay up to three pinned-SHA content GETs after checking /rate_limit",
    )
    parser.add_argument(
        "--tool",
        help="replay only this tool; existing results for other tools are retained in the report",
    )
    args = parser.parse_args()
    report = asyncio.run(run(args.anonymous_pinned_content, args.tool))
    print_table(report)
    print("Mode:", report["mode"])
    print("Rate limits before replay:", json.dumps(report["rate_limits_before_replay"], sort_keys=True))
    print("Tool list match:", report["tool_list_match"])
    print("Skipped records:", json.dumps(report["skipped_record_counts"], sort_keys=True))


if __name__ == "__main__":
    main()
