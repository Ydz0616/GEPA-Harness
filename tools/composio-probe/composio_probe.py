import asyncio, time, sys
from hidden_layer.config import Settings
from hidden_layer import db
from hidden_layer.tools import composio

async def main(n: int, timeout_s: float):
    s = Settings()
    pool = db.pg_pool(s)
    url = composio.resolve_mcp_url(pool)
    srv = composio.make_mcp_server(url, s.composio_api_key, toolkit=composio.GITHUB_TOOLKIT,
                                   timeout_s=timeout_s, full_surface=True)
    async with srv:
        t = time.monotonic(); tools = (await srv.session.list_tools()).tools
        print(f"list_tools {len(tools)} {time.monotonic()-t:.1f}s", flush=True)
        calls = [("GITHUB_GET_A_COMMIT", {"owner": "sanic-org", "repo": "sanic", "ref": "main"}),
                 ("GITHUB_GET_REPOSITORY_CONTENT", {"owner": "sanic-org", "repo": "sanic", "path": "README.rst"})]
        for i in range(n):
            name, args = calls[i % 2]
            t = time.monotonic()
            try:
                r = await srv.session.call_tool(name, args)
                txt = str(r.content[0].text if r.content else "")[:80].replace("\n", " ")
                print(f"{i} {name} ok {time.monotonic()-t:.1f}s {txt}", flush=True)
            except Exception as e:
                print(f"{i} {name} ERR {time.monotonic()-t:.1f}s {type(e).__name__}: {str(e)[:120]}", flush=True)

asyncio.run(main(int(sys.argv[1]), float(sys.argv[2])))
