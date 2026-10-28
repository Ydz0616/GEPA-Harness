#!/home/ubuntu/repos/Hidden-Layer-Internal/.venv/bin/python
"""Read-only GitHub REST-backed clone of the captured Composio MCP surface."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import string
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool
from starlette.applications import Starlette
from starlette.routing import Mount

TOOLS_PATH = Path("/home/ubuntu/improve-runs/probe/composio_tools.json")
GITHUB_API = "https://api.github.com"
COMPOSIO_VERSION = "20261014_00"
ISSUE_SEARCH_MESSAGE = (
    "Minimal response: returning optimized issue/PR fields. "
    "Use response_detail='full' for the complete GitHub API response with all nested objects."
)
CODE_SEARCH_SEMAPHORE = asyncio.Semaphore(1)
CODE_SEARCH_MIN_INTERVAL_S = 6.1
last_code_search_at = 0.0
WRITE_TOOLS = {
    "GITHUB_CREATE_AN_ISSUE",
    "GITHUB_CREATE_AN_ISSUE_COMMENT",
    "GITHUB_UPDATE_AN_ISSUE",
    "GITHUB_LIST_REPOSITORIES_FOR_THE_AUTHENTICATED_USER",
}


def load_tools() -> list[Tool]:
    raw_tools = json.loads(TOOLS_PATH.read_text())
    return [Tool.model_validate(tool) for tool in raw_tools]


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def envelope(
    data: Any = None,
    *,
    error: str | None = None,
    http_status: int = 200,
    successful: bool | None = None,
) -> str:
    ok = error is None if successful is None else successful
    log_id = "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(16)
    )
    return compact_json({
        "successfull": ok,
        "error": error,
        "data": data,
        "version": COMPOSIO_VERSION,
        "auth_refresh_required": False,
        "mercury_last_http_status_code": http_status,
        "is_latest_version": True,
        "successful": ok,
        "log_id": log_id,
    })


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


async def get_github_response(
    client: httpx.AsyncClient,
    path: str,
    *,
    params: dict[str, Any] | None,
    headers: dict[str, str],
) -> httpx.Response:
    response = await client.get(f"{GITHUB_API}{path}", params=params, headers=headers)
    if response.status_code == 401:
        token = await asyncio.to_thread(read_github_token)
        if token:
            headers["Authorization"] = f"token {token}"
            response = await client.get(
                f"{GITHUB_API}{path}", params=params, headers=headers
            )
    return response


def github_error(response: httpx.Response) -> str:
    error = response.text
    if not error:
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                payload = {"message": response.reason_phrase}
        except ValueError:
            payload = {"message": response.reason_phrase}
        error = json.dumps(payload, ensure_ascii=False, indent="\t")
    category = "Client Error" if response.status_code < 500 else "Server Error"
    data = {
        "http_error": (
            f"{response.status_code} {category}: {response.reason_phrase} "
            f"for url: {response.url}"
        ),
        "message": error,
        "status_code": response.status_code,
    }
    return envelope(
        data,
        error=error,
        http_status=response.status_code,
        successful=False,
    )


def api_path(owner: str, repo: str, suffix: str) -> str:
    return f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}/{suffix}"


def pagination(args: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("page", "per_page"):
        if key in args:
            result[key] = args[key]
    return result


def find_pull_request_query(args: dict[str, Any]) -> str:
    terms = ["is:pr"]
    query = args.get("query")
    if query:
        terms.append(str(query))

    owner, repo = args.get("owner"), args.get("repo")
    if repo:
        repository = str(repo)
        if owner and "/" not in repository:
            repository = f"{owner}/{repository}"
        terms.append(f"repo:{repository}")
    elif owner:
        terms.append(f"user:{owner}")

    for key, qualifier in (
        ("label", "label"),
        ("author", "author"),
        ("assignee", "assignee"),
        ("language", "language"),
        ("mentions", "mentions"),
        ("base_branch", "base"),
        ("head_branch", "head"),
    ):
        if args.get(key) is not None:
            terms.append(f"{qualifier}:{args[key]}")

    state = args.get("state")
    if state in {"open", "closed"}:
        terms.append(f"is:{state}")
    if args.get("is_merged") is True:
        terms.append("is:merged")
    elif args.get("is_merged") is False:
        terms.append("is:unmerged")
    for key in ("created_since", "updated_since"):
        if args.get(key):
            terms.append(f"{'created' if key == 'created_since' else 'updated'}:>={args[key]}")
    if args.get("for_authenticated_user") and not owner and not repo:
        terms.append("user:@me")
    return " ".join(terms)


def request_for_tool(name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    owner = str(args.get("owner", ""))
    repo = str(args.get("repo", ""))
    params: dict[str, Any] = {}

    if name == "GITHUB_CHECK_IF_PULL_REQUEST_HAS_BEEN_MERGED":
        return api_path(owner, repo, f"pulls/{args['pull_number']}/merge"), {}
    if name == "GITHUB_FIND_PULL_REQUESTS":
        params = {
            "q": find_pull_request_query(args),
            **pagination(args),
            **{key: args[key] for key in ("sort", "order") if key in args},
        }
        return "/search/issues", params
    if name == "GITHUB_GET_A_BRANCH":
        return api_path(owner, repo, f"branches/{quote(str(args['branch']), safe='')}"), {}
    if name == "GITHUB_GET_A_COMMIT":
        params = pagination(args)
        return api_path(owner, repo, f"commits/{quote(str(args['ref']), safe='')}"), params
    if name == "GITHUB_GET_AN_ISSUE":
        return api_path(owner, repo, f"issues/{args['issue_number']}"), {}
    if name == "GITHUB_GET_A_PULL_REQUEST":
        return api_path(owner, repo, f"pulls/{args['pull_number']}"), {}
    if name == "GITHUB_GET_A_REPOSITORY":
        return f"/repos/{quote(owner, safe='')}/{quote(repo, safe='')}", {}
    if name == "GITHUB_GET_A_REPOSITORY_README":
        params = {"ref": args["ref"]} if args.get("ref") else {}
        return api_path(owner, repo, "readme"), params
    if name == "GITHUB_GET_A_TREE":
        params = {"recursive": "1"} if args.get("recursive") else {}
        return api_path(owner, repo, f"git/trees/{quote(str(args['tree_sha']), safe='')}"), params
    if name == "GITHUB_GET_REPOSITORY_CONTENT":
        path = str(args["path"]).strip("/")
        suffix = "contents" + (f"/{quote(path, safe='/')}" if path else "")
        params = {"ref": args["ref"]} if args.get("ref") else {}
        return api_path(owner, repo, suffix), params
    if name == "GITHUB_LIST_BRANCHES":
        params = pagination(args)
        return api_path(owner, repo, "branches"), params
    if name == "GITHUB_LIST_COMMITS":
        params = pagination(args)
        for key in ("sha", "path", "since", "until", "author", "committer"):
            if key in args:
                params[key] = args[key]
        return api_path(owner, repo, "commits"), params
    if name == "GITHUB_LIST_COMMITS_ON_A_PULL_REQUEST":
        params = pagination(args)
        return api_path(owner, repo, f"pulls/{args['pull_number']}/commits"), params
    if name == "GITHUB_LIST_ORGANIZATION_REPOSITORIES":
        params = pagination(args)
        for key in ("sort", "type", "direction"):
            if key in args:
                params[key] = args[key]
        return f"/orgs/{quote(str(args['org']), safe='')}/repos", params
    if name == "GITHUB_LIST_PULL_REQUESTS":
        params = pagination(args)
        for key in ("base", "head", "sort", "state", "direction"):
            if key in args:
                params[key] = args[key]
        return api_path(owner, repo, "pulls"), params
    if name == "GITHUB_LIST_PULL_REQUESTS_FILES":
        params = pagination(args)
        return api_path(owner, repo, f"pulls/{args['pull_number']}/files"), params
    if name == "GITHUB_LIST_REPOSITORY_ISSUES":
        params = pagination(args)
        for key in (
            "sort", "type", "since", "state", "labels", "creator", "assignee",
            "direction", "mentioned", "milestone",
        ):
            if key in args:
                value = args[key]
                if key == "labels" and isinstance(value, list):
                    value = ",".join(str(label) for label in value)
                params[key] = value
        return api_path(owner, repo, "issues"), params
    if name == "GITHUB_LIST_REVIEW_COMMENTS_ON_A_PULL_REQUEST":
        params = pagination(args)
        for key in ("sort", "since", "direction"):
            if key in args:
                params[key] = args[key]
        return api_path(owner, repo, f"pulls/{args['pull_number']}/comments"), params
    if name == "GITHUB_LIST_REVIEWS_FOR_A_PULL_REQUEST":
        return api_path(owner, repo, f"pulls/{args['pull_number']}/reviews"), pagination(args)
    if name == "GITHUB_SEARCH_CODE":
        params = {"q": args["q"], **pagination(args)}
        for key in ("sort", "order"):
            if key in args:
                params[key] = args[key]
        return "/search/code", params
    if name == "GITHUB_SEARCH_ISSUES_AND_PULL_REQUESTS":
        params = {"q": args["q"], **pagination(args)}
        for key in ("sort", "order"):
            if key in args:
                params[key] = args[key]
        return "/search/issues", params
    if name == "GITHUB_SEARCH_REPOSITORIES":
        params = {"q": args["q"], **pagination(args)}
        for key in ("sort", "order"):
            if key in args:
                params[key] = args[key]
        return "/search/repositories", params
    raise ValueError(f"Unsupported read tool: {name}")


async def github_call(name: str, args: dict[str, Any]) -> str:
    if name == "GITHUB_SEARCH_CODE":
        async with CODE_SEARCH_SEMAPHORE:
            return await _github_call(name, args, rate_limit_code_search=True)
    return await _github_call(name, args)


async def _github_call(
    name: str,
    args: dict[str, Any],
    *,
    rate_limit_code_search: bool = False,
) -> str:
    global last_code_search_at
    path, params = request_for_tool(name, args)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ghshim-local-read-only-mcp",
    }
    token = await asyncio.to_thread(read_github_token)
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=False) as client:
            if rate_limit_code_search:
                rate_response = await get_github_response(
                    client, "/rate_limit", params=None, headers=headers
                )
                if rate_response.is_error:
                    return github_error(rate_response)
                resources = rate_response.json().get("resources", {})
                code_search = resources.get("code_search") or resources.get("search")
                if not isinstance(code_search, dict):
                    return envelope(
                        error="GitHub code search rate limit is unavailable",
                        http_status=503,
                        successful=False,
                    )
                if int(code_search.get("remaining", 0)) <= 0:
                    message = "GitHub code search rate limit is exhausted"
                    error = json.dumps(
                        {"message": message, "status": "403"},
                        ensure_ascii=False,
                        indent="\t",
                    )
                    data = {
                        "http_error": "403 Client Error: Forbidden for code search",
                        "message": error,
                        "status_code": 403,
                    }
                    return envelope(
                        data, error=error, http_status=403, successful=False
                    )
                limit = max(int(code_search.get("limit", 10)), 1)
                min_interval = max(CODE_SEARCH_MIN_INTERVAL_S, 60 / limit + 0.1)
                delay = min_interval - (time.monotonic() - last_code_search_at)
                if delay > 0:
                    await asyncio.sleep(delay)
                last_code_search_at = time.monotonic()
            response = await get_github_response(
                client, path, params=params, headers=headers
            )
    except httpx.TimeoutException:
        return envelope(
            {"http_error": "GitHub API request timed out after 20 seconds",
             "message": "GitHub API request timed out after 20 seconds",
             "status_code": 0},
            error="GitHub API request timed out after 20 seconds",
            http_status=0,
            successful=False,
        )
    except httpx.HTTPError as exc:
        error = f"GitHub API request failed: {type(exc).__name__}"
        return envelope(
            {"http_error": error, "message": error, "status_code": 0},
            error=error,
            http_status=0,
            successful=False,
        )

    if name == "GITHUB_CHECK_IF_PULL_REQUEST_HAS_BEEN_MERGED":
        if response.status_code in (204, 404):
            return envelope(
                {"merged": response.status_code == 204},
                http_status=response.status_code,
            )
    if response.is_error:
        return github_error(response)
    if response.status_code == 204 or not response.content:
        data: Any = None
    else:
        try:
            data = response.json()
        except ValueError:
            return envelope(error="GitHub API returned a non-JSON response")

    if name == "GITHUB_LIST_BRANCHES" and "protected" in args:
        if not isinstance(data, list):
            return envelope(error="GitHub returned an unexpected branch response")
        data = [branch for branch in data if branch.get("protected") is args["protected"]]
    if name == "GITHUB_GET_REPOSITORY_CONTENT":
        data = {"content": data}
    if name == "GITHUB_SEARCH_ISSUES_AND_PULL_REQUESTS" and isinstance(data, dict):
        data = {
            "composio_execution_message": ISSUE_SEARCH_MESSAGE,
            **{key: data[key] for key in sorted(data)},
        }
    return envelope(data)


async def call_tool(name: str, args: dict[str, Any]) -> str:
    started = time.perf_counter()
    status = "error"
    try:
        if name in WRITE_TOOLS:
            message = "This local GitHub shim is read-only"
            error = json.dumps({"message": message, "status": "403"}, indent="\t")
            result = envelope(
                {"http_error": f"403 Client Error: Forbidden for {name}",
                 "message": error, "status_code": 403},
                error=error,
                http_status=403,
                successful=False,
            )
        elif name == "COMPOSIO_CHECK_ACTIVE_CONNECTION":
            result = envelope({"connected": bool(await asyncio.to_thread(read_github_token))})
        elif name == "COMPOSIO_GET_REQUIRED_PARAMETERS":
            result = envelope({"parameters": []})
        elif name == "COMPOSIO_INITIATE_CONNECTION":
            result = envelope({
                "success": False,
                "message": "Connection setup is not available on the local GitHub shim.",
            }, successful=False)
        else:
            result = await github_call(name, args)
        try:
            status = "ok" if json.loads(result).get("successfull") is True else "error"
        except (AttributeError, TypeError, ValueError):
            status = "error"
        return result
    except (KeyError, TypeError, ValueError) as exc:
        status = f"invalid_{type(exc).__name__}"
        return envelope(error=f"Invalid arguments for {name}")
    finally:
        latency_ms = (time.perf_counter() - started) * 1000
        print(f"tool={name} status={status} latency_ms={latency_ms:.1f}", flush=True)


tools = load_tools()
server = Server(
    "composio-github-readonly-shim",
    on_list_tools=lambda _ctx, _params: asyncio.sleep(
        0, result=ListToolsResult(tools=tools)
    ),
    on_call_tool=lambda _ctx, params: _call_tool_result(params.name, params.arguments or {}),
)


async def _call_tool_result(name: str, args: dict[str, Any]) -> CallToolResult:
    text = await call_tool(name, args)
    try:
        is_error = json.loads(text).get("successfull") is False
    except (AttributeError, TypeError, ValueError):
        is_error = True
    return CallToolResult(content=[TextContent(text=text)], is_error=is_error)


session_manager = StreamableHTTPSessionManager(server, stateless=False)


@asynccontextmanager
async def lifespan(_app: Starlette):
    async with session_manager.run():
        yield


app = Starlette(routes=[Mount("/mcp", app=session_manager.handle_request)], lifespan=lifespan)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765, access_log=False, log_level="info")
