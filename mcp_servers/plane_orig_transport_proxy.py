import sys
from pathlib import Path
from subprocess import run

from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs

BUILD_SCRIPT = """#!/usr/bin/env bash

curl -OLJ https://github.com/makeplane/plane-mcp-server/archive/refs/tags/v0.1.4.tar.gz
tar -xf plane-mcp-server-0.1.4.tar.gz
rm plane-mcp-server-0.1.4.tar.gz
mv plane-mcp-server-0.1.4 .pinned_plane_mcp
cd .pinned_plane_mcp
npm ci
npm run build
"""


def ensure_server_is_built():
    repo_root = Path(__file__).parent.joinpath(".pinned_plane_mcp")
    index_path = repo_root / "build/index.js"
    if index_path.exists():
        return "mcp_servers/.pinned_plane_mcp/build/index.js"
    with open(Path(__file__).parent.joinpath("_build_script.sh"), "w") as f:
        f.write(BUILD_SCRIPT)
    run(
        ["bash", "_build_script.sh"],
        cwd=Path(__file__).parent.absolute().resolve().as_posix(),
        check=True,
    )
    Path(__file__).parent.joinpath("_build_script.sh").unlink()
    assert index_path.exists()
    return "mcp_servers/.pinned_plane_mcp/build/index.js"


server_file = ensure_server_is_built()

config = {
    "mcpServers": {
        "plane": {
            "command": "node",
            "args": [server_file],
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
