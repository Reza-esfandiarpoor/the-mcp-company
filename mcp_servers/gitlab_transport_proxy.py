import sys
from pathlib import Path
from subprocess import run

from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs

BUILD_SCRIPT = """#!/usr/bin/env bash

curl -OLJ https://github.com/zereight/gitlab-mcp/archive/refs/tags/v2.0.3.tar.gz
tar -xf gitlab-mcp-2.0.3.tar.gz
rm gitlab-mcp-2.0.3.tar.gz
mv gitlab-mcp-2.0.3 .pinned_gitlab_mcp
cd .pinned_gitlab_mcp
npm ci
npm run build
"""


def ensure_server_is_built():
    repo_root = Path(__file__).parent.joinpath(".pinned_gitlab_mcp")
    index_path = repo_root / "build/index.js"
    if index_path.exists():
        return "mcp_servers/.pinned_gitlab_mcp/build/index.js"
    with open(Path(__file__).parent.joinpath("_build_script.sh"), "w") as f:
        f.write(BUILD_SCRIPT)
    run(
        ["bash", "_build_script.sh"],
        cwd=Path(__file__).parent.absolute().resolve().as_posix(),
        check=True,
    )
    Path(__file__).parent.joinpath("_build_script.sh").unlink()
    assert index_path.exists()
    return "mcp_servers/.pinned_gitlab_mcp/build/index.js"


server_file = ensure_server_is_built()

config = {
    "mcpServers": {
        "GitLab communication server": {
            "command": "node",
            "args": [server_file],
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
