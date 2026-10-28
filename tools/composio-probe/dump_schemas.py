import asyncio, json
from hidden_layer.config import Settings
from hidden_layer import db
from hidden_layer.tools import composio

async def main():
    s = Settings(); pool = db.pg_pool(s)
    url = composio.resolve_mcp_url(pool)
    srv = composio.make_mcp_server(url, s.composio_api_key, toolkit=composio.GITHUB_TOOLKIT, timeout_s=180, full_surface=True)
    async with srv:
        tools = (await srv.session.list_tools()).tools
        json.dump([t.model_dump(mode="json") for t in tools], open("/home/ubuntu/improve-runs/probe/composio_tools.json", "w"), indent=1)
        print(len(tools), [t.name for t in tools])

asyncio.run(main())
