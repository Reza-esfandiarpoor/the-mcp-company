_This is a clone of [OpenHands](https://github.com/All-Hands-AI/OpenHands) from commit `91cd647f207ccf30c09e1ebf99ac6c3c22cfda64`, with some modifications for implementing MCPAgent._

## Setup

Make sure you are are in this directory (`cd OpenHands` from root of the repo) before running the setup process.
Follow [these instructions](Development.md) to set up a development environment for evaluation. Here is the summary:

- Make sure docker and poetry are installed and you have `python==3.12`, `NodeJS >= 22.x`.
- On ubuntu, you also need `build-essential` (`sudo apt install build-essential`). On WSL, you need netcat (`apt install netcat`).
- Run `make build`. It will take a while to finish.

## Run Evaluations

For experiments with tool retrieval or oracle tool set, first make sure the correct MCP server is running before proceeding (instructions are [here](../mcp_servers/README.md)).
Also for all experiments, set your LLM configuration (e.g., model name, authentication token, etc.) in `config.toml` under `[llm.agent]` key.

### TheAgentCompany Tasks

**Agent with access to Browser tool**

Make the following changes to `config.toml` file:

- Under `[agent]` set `system_prompt_filename='system_prompt_cua.j2'`

From this directory run `bash run_all_agc.sh cua`

**Agent with access to oracle tool set**

Make the following changes to `config.toml` file:

- Under `[agent]` set `system_prompt_filename='system_prompt_gt_tools.j2'`
- Under `[agent]` set `enable_browsing=false`
- Uncomment lines:
  ```bash
  [mcp]
  sse_servers = ["http://localhost:7879/sse"]
  ```

From this directory run `bash run_all_agc.sh gt_tools`

**Agent with tool retrieval (MCPAgent)**

Make the following changes to `config.toml` file:

- Under `[agent]` set `system_prompt_filename='system_prompt_find_tools.j2'`
- Under `[agent]` set `enable_browsing=false`
- Uncomment lines:
  ```bash
  [mcp]
  sse_servers = ["http://localhost:7879/sse"]
  ```

From this directory run `bash run_all_agc.sh dense_retrieval`

### Azure Tasks

Make sure the MCP server with tool retrieval is running.
set your LLM configuration (e.g., model name, authentication token, etc.) in `config.toml` under `[llm.agent]` key.

Make the following changes to `config.toml` file:

- Under `[agent]` set `system_prompt_filename='system_prompt_find_tools.j2'`
- Under `[agent]` set `enable_browsing=false`
- Uncomment lines:
  ```bash
  [mcp]
  sse_servers = ["http://localhost:7879/sse"]
  ```

From this directory run `RUN_AZURE_TASKS=true bash run_all_agc.sh dense_retrieval`
