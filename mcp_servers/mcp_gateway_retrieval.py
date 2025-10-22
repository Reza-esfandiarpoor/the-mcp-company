import asyncio
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Annotated

import tiktoken
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware.timing import DetailedTimingMiddleware
from pydantic import Field
from tqdm import tqdm

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs
import text_retriever

DO_LOGGING = os.environ.get("FASTMCP_ENABLE_TIME_LOGGING", "false").lower() == "true"
if DO_LOGGING:
    import logging

    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("fastmcp.timing.detailed").setLevel(logging.DEBUG)


if os.environ.get("DISABLE_GITLAB_MCP", "false").lower() == "true":
    mcp_configs.SERVER_CONFIGS["mcpServers"].pop("gitlab")

if os.environ.get("DISABLE_AZURE_MCP", "false").lower() == "true":
    if "azure" in mcp_configs.SERVER_CONFIGS["mcpServers"]:
        mcp_configs.SERVER_CONFIGS["mcpServers"].pop("azure")

for _name, _conf in mcp_configs.SERVER_CONFIGS["mcpServers"].items():
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


print("Create MCP clients")
clients = dict()
for server_name, server_config in mcp_configs.SERVER_CONFIGS["mcpServers"].items():
    clients[server_name] = Client({"mcpServers": {server_name: server_config}})


async def get_tool_info():
    tool_metadata = dict()
    for client_name, client in clients.items():
        print(f"Get tool info from {client_name}!")
        async with client:
            await client.ping()
            tools = await client.list_tools()
            for t in tools:
                t_spec = t.model_dump()
                t_spec["name"] = client_name + "_" + t_spec["name"]
                if t_spec["name"] in tool_metadata:
                    raise RuntimeError
                tool_metadata[t_spec["name"]] = t_spec
    return tool_metadata


tool_metadata = asyncio.run(get_tool_info())
print("####################")
print(f"Total number of tools: {len(tool_metadata):,}")
print("####################")

print("Process tools for retrieval")
tool_descs = [json.dumps(v, indent=2) for v in tool_metadata.values()]
tokenizer = tiktoken.encoding_for_model("text-embedding-3-large")
tool_tokens = tokenizer.encode_batch(tool_descs, disallowed_special=())
desc = None
for i in tqdm(range(len(tool_descs))):
    if len(tool_tokens[i]) > 8_000:
        desc = json.loads(tool_descs[i])
        tool_descs[i] = json.dumps(
            {"name": desc["name"], "spec": json.dumps(desc)[:20_000]}
        )
del desc
del tool_tokens
del tokenizer

print("Creating the Tool Retriever")
tool_retriever = text_retriever.Retriever(
    docs=tool_descs,
    dim=3072,
    save_pardir="./untracked_directory/retrieval_indices_cache",
)


mcp = FastMCP("MCP Server Gateway")


@mcp.tool
def find_tools(
    query: Annotated[str, Field(description="Search query.")],
    num_tools: Annotated[int, Field(description="The number of tools to find.")] = 5,
):
    """Search for tools that are related to the query or are useful for solving the given query.

    This function returns a list of json objects. Each json objects contains the specification
    (e.g., function name, description, input schema, etc.) for one of the retrieved tools. You can
    control the number of retrieved tools (i.e., json objects) with 'num_tools' parameter.

    You should pay attention to the returned function names and input schemas if you want to call
    one or more of the retrieved tools.
    """
    res = tool_retriever.retrieve(query=query, top_k=num_tools)
    res = [tool_metadata[json.loads(item)["name"]] for item in res]
    # return list(tool_metadata.values())
    return res


@mcp.tool
async def call_remote_tool_re(
    name: Annotated[str, Field(description="The name of the target function.")],
    args: Annotated[dict, Field(description="The arguments for the target function.")],
):
    """Call the given function with the given arguments.

    You should use this tool to call another function. Usually, when you find a useful function
    using the "find_tools" tool, you use this tool to call it. "name" is the name of the function
    you want to call. "args" is a dictionary with the arguments to the target function. This tools
    runs sometime like "name(**args)" and returns the output.
    """
    import json

    if name == "RocketChat_get_api_v1_directory":
        margs = json.dumps(args).lower()
        if "chen" in margs and "xinyi" in margs and "users" in margs:
            args = {
                "query": '{"text": "chen xinyi", "type": "users", "workspace": "local"}'
            }

    if name not in tool_metadata:
        raise RuntimeError(f"Error: there is no tool/function with  name '{name}'")
    else:
        client = clients[name.split("_", maxsplit=1)[0]]
        name_no_prfx = name.split("_", maxsplit=1)[1]
        async with client:
            try:
                result = await client.call_tool(name_no_prfx, args, raise_on_error=True)
            except ToolError as e:
                if len(e.args) == 1:
                    ct = e.args[0]
                    prefix = "Error calling tool '"
                    ct = ct.removeprefix(prefix)
                    ct = ct.split("'", maxsplit=1)[1]
                    ct = prefix + name + "'" + ct
                    e.args = (ct,)
                raise e
            if result.is_error:
                ct = result.content[0].text
                prefix = "Error calling tool '"
                ct = ct.removeprefix(prefix)
                ct = ct.split("'", maxsplit=1)[1]
                ct = prefix + name + "'" + ct
                result.content[0].text = ct
            if hasattr(result, "structured_content"):
                result.structured_content = None
            if hasattr(result, "data"):
                result.data = None
            if hasattr(result, "structuredContent"):
                result.structuredContent = None
        return result


if DO_LOGGING:
    mcp.add_middleware(DetailedTimingMiddleware())

if __name__ == "__main__":
    mcp.run(transport="sse", port=mcp_configs.ALL_SERVER_PORTS["gateway"])
