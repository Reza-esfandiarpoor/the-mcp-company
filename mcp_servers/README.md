# MCP Servers

## TheAgentCompany Services

There are two options for running the MCP servers for Plane, GitLab, ownCloud, and RocketChat.

**Docker**

- cd to this directory (`cd mcp_servers`)
- run `docker compose up -d` (It takes a while for the servers to load)

**Manual**

- Create a virtual environment with `python==3.12`
- Install the necessary packages: `pip install 'fastmcp==2.11.2' 'PyYAML==6.0.2' 'webdav4==0.10.0' 'mcp==1.12.3'`
- Run the MCP servers in the background (e.g., run each command in a TMUX session in the background)
  ```bash
  # Each command is one MCP server and is blocking
  # You should run each one of these in a separate shell
  python mcp_servers/plane_orig_transport_proxy.py
  python mcp_servers/plane_mcp.py
  python mcp_servers/rocket_chat_mcp.py
  python mcp_servers/webdav_mcp.py
  python mcp_servers/gitlab_openapi.py
  python mcp_servers/gitlab_transport_proxy.py
  python mcp_servers/gitlab_mcp.py
  ```

## Azure

To run the MCP server for Azure:

- Follow the instructions in [here](../azure_tasks/README.md) to get the credentials and create the necessary files
- Create a virtual environment with `python==3.12` and install the requirements: `pip install -r requirements.txt`
- From the root of the repo, run `bash mcp_servers/azure_v2/run_azure_mcp.sh` (make sure your environment is active when running this command).

**Note**: It takes a while for the server to parse all OpenAPI Specs (up to 10 minutes).

## MCP Gateway

First, you need to create the python environment. You can use the same environment from the Azure MCP server setup above if you have created one. Or create a new virtual environment with `python==3.12` and install the requirements: `pip install -r requirements.txt`

There are two ways for exposing the tools to the agent.

#### Oracle Tool Set

Activate the environment and run the following from the root of the repo:

```bash
# export DISABLE_AZURE_MCP=false
python mcp_servers/mcp_preselected_tools.py
```

If you are not running the Azure MCP server, uncomment `export DISABLE_AZURE_MCP=false`.

This runs an MCP server on port `7879` and also provides a `/admin/set_tools` endpoint that takes a list of tool names and only exposes those tools and hides the rest from the agent.

#### Tool Retrieval

Set your OpenAI API key for accessing the embedding model.

Activate the environment and from the root of the repo run:

```bash
# export DISABLE_AZURE_MCP=false
export OPENAI_API='...'
python mcp_servers/mcp_gateway_retrieval.py
```
If you are not running the Azure MCP server, uncomment `export DISABLE_AZURE_MCP=false`.

**Note**: If you are encoding the full tool set (including Azure tools), it will take a while to calculate the embedding for all tool specifications.
