import sys
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs

config = {
    "mcpServers": {
        "plane": {
            "command": "npx",
            "args": ["-y", "@makeplane/plane-mcp-server@0.1.4"],
            "env": {
                "PLANE_API_KEY": mcp_configs.TAC_SERVICES["plane"]["token"],
                "PLANE_API_HOST_URL": mcp_configs.TAC_SERVICES["plane"]["url"].strip(
                    "/"
                ),
                "PLANE_WORKSPACE_SLUG": "tac",
            },
        },
    }
}

local_proxy = FastMCP.as_proxy(ProxyClient(config), name="Plane Official Server")

if __name__ == "__main__":
    local_proxy.run(
        transport="sse", port=mcp_configs.ALL_SERVER_PORTS["plane_transport_proxy"]
    )
