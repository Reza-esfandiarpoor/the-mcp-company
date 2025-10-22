import os
import socket
import sys
import time
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import NotFoundError
from fastmcp.tools import Tool
from starlette.requests import Request
from starlette.responses import JSONResponse

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs

if os.environ.get("DISABLE_GITLAB_MCP", "false").lower() == "true":
    mcp_configs.SERVER_CONFIGS["mcpServers"].pop("gitlab")

if os.environ.get("DISABLE_AZURE_MCP", "false").lower() == "true":
    if "azure" in mcp_configs.SERVER_CONFIGS["mcpServers"]:
        mcp_configs.SERVER_CONFIGS["mcpServers"].pop("azure")

proxy_names = list(sorted(list(mcp_configs.SERVER_CONFIGS["mcpServers"].keys())))

for _name in proxy_names:
    _conf = mcp_configs.SERVER_CONFIGS["mcpServers"][_name]
    print(f"Check if {_name} server is up!")
    if _conf.get("transport", None) != "sse":
        continue

    _port = int(_conf["url"].removesuffix("/sse").split(":")[-1])
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("localhost", _port))
        sock.close()
        if result != 0:
            print(f"Waiting for {_name} server to respond.")
            time.sleep(2)
        else:
            break
time.sleep(2)

print("Create MCP proxies")
proxies = dict()
for server_name in proxy_names:
    server_config = mcp_configs.SERVER_CONFIGS["mcpServers"][server_name]
    proxies[server_name] = FastMCP.as_proxy(
        {"mcpServers": {server_name: server_config}}
    )

main_server = FastMCP("MCP Proxy")


@main_server.custom_route("/admin/set_tools", methods=["POST"])
async def set_tools(req: Request):
    body = await req.json()
    target_tools = body["tool_names"]

    all_tools = await main_server.get_tools()
    for tname in all_tools:
        main_server.remove_tool(tname)

    added_tools = list()
    for tool_name in target_tools:
        name = tool_name.split("_", maxsplit=1)[1]
        proxy_name = tool_name.split("_", maxsplit=1)[0]
        proxy = proxies[proxy_name]
        try:
            tool = await proxy.get_tool(name)
        except NotFoundError:
            continue
        new_tool = Tool.from_tool(tool.copy(), name=proxy_name + "_" + tool.name)
        main_server.add_tool(new_tool)
        added_tools.append(new_tool.name)
    return JSONResponse(added_tools)


if __name__ == "__main__":
    main_server.run(transport="sse", port=mcp_configs.ALL_SERVER_PORTS["gateway"])
