import sys
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs

config = {
    "mcpServers": {
        "GitLab communication server": {
            "command": "npx",
            "args": ["-y", "@zereight/mcp-gitlab@2.0.3"],
            "env": {
                "GITLAB_PERSONAL_ACCESS_TOKEN": mcp_configs.TAC_SERVICES["gitlab"][
                    "token"
                ],
                "GITLAB_API_URL": f"{mcp_configs.TAC_SERVICES['gitlab']['url'].strip('/')}/api/v4",
                "GITLAB_READ_ONLY_MODE": "false",
                "USE_GITLAB_WIKI": "true",
                "USE_MILESTONE": "true",
                "USE_PIPELINE": "true",
                "GITLAB_IS_OLD": "true",
            },
        }
    }
}

local_proxy = FastMCP.as_proxy(ProxyClient(config), name="GitLab Existing MCP Server")

if __name__ == "__main__":
    local_proxy.run(
        transport="sse", port=mcp_configs.ALL_SERVER_PORTS["gitlab_transport_proxy"]
    )
