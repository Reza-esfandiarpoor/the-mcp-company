import os

os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"

import asyncio
import hashlib
import sys
import urllib
from contextlib import contextmanager
from pathlib import Path

import httpx
import yaml
from fastmcp import FastMCP
from fastmcp.tools import Tool
from fastmcp.tools.tool_transform import forward

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs


@contextmanager
def server_duplicate_behavior(curr_server, new_behavior):
    old_behavior = curr_server._tool_manager.duplicate_behavior

    curr_server._tool_manager.duplicate_behavior = new_behavior
    try:
        yield
    finally:
        curr_server._tool_manager.duplicate_behavior = old_behavior


def load_yaml(file: str | Path):
    with open(file, "r") as f:
        obj = yaml.load(f, Loader=yaml.CSafeLoader)
    return obj


def add_summary_to_desc(spec: dict) -> dict:
    """Prepends the summary to description for each path in the OpenAPI spec."""
    for k, path_spec in spec["paths"].items():
        for req_type, req_spec in path_spec.items():
            if "summary" in req_spec and "description" in req_spec:
                new_desc = req_spec["summary"] + "\n\n" + req_spec["description"]
                spec["paths"][k][req_type]["description"] = new_desc
    return spec


def clean_operation_id(spec: dict) -> dict:
    """Remove apiv4 from Operation ID field."""
    for k, path_spec in spec["paths"].items():
        for req_type, req_spec in path_spec.items():
            if "operationId" in req_spec:
                opid = req_spec["operationId"]
                opid = opid.replace("ApiV4", "")
                spec["paths"][k][req_type]["operationId"] = opid
    return spec


def remove_response_schema(spec: dict) -> dict:
    for path, path_data in spec["paths"].items():
        for method, method_data in path_data.items():
            if "responses" not in method_data:
                continue
            for resp, resp_data in method_data["responses"].items():
                if "content" not in resp_data:
                    continue
                for content, content_data in resp_data["content"].items():
                    if "schema" in content_data:
                        del spec["paths"][path][method]["responses"][resp]["content"][
                            content
                        ]["schema"]
    return spec


def spec_processing(spec: dict) -> dict:
    spec = clean_operation_id(spec)
    spec = add_summary_to_desc(spec)
    spec = remove_response_schema(spec)
    return spec


def _url_encode_str(x) -> str:
    if not isinstance(x, str):
        return x
    return urllib.parse.quote(urllib.parse.unquote(x), safe="")


async def url_encode_wrapper(**kwargs):
    path_params = kwargs.pop("____re_path_params")
    for k in kwargs.keys():
        if k in path_params:
            kwargs[k] = _url_encode_str(kwargs[k])
    res = await forward(**kwargs)
    res.structured_content = None
    return res


def find_path_params(tool):
    path_params = []
    if not hasattr(tool, "_route"):
        return path_params
    for param in tool._route.parameters:
        if param.location == "path":
            path_params.append(param.name)
    return path_params


def make_async_partial(func, **kwargs):
    async def wrapped(**more_kwargs):
        return await func(**{**kwargs, **more_kwargs})

    return wrapped


client = httpx.AsyncClient(
    base_url=mcp_configs.TAC_SERVICES["gitlab"]["url"],
    headers={"PRIVATE-TOKEN": mcp_configs.TAC_SERVICES["gitlab"]["token"]},
)

spec_path = (
    Path(__file__).parents[1].joinpath("data/api_specs/gitlab_api/openapi_v3.yaml")
)
spec = load_yaml(spec_path)

spec = spec_processing(spec)
mcp = FastMCP.from_openapi(openapi_spec=spec, client=client, name="GitLab Server")

all_tools = asyncio.run(mcp.get_tools())
for tool in all_tools.values():
    from_tool_kwargs = dict()
    from_tool_kwargs["transform_fn"] = make_async_partial(
        url_encode_wrapper, ____re_path_params=find_path_params(tool)
    )
    if len(tool.name) >= 57:
        name_hash = hashlib.sha256(tool.name.encode()).hexdigest()[:4]
        new_name = name_hash + tool.name[-45:]
        from_tool_kwargs["name"] = new_name

    new_tool = Tool.from_tool(tool, **from_tool_kwargs)

    if "name" in from_tool_kwargs:
        mcp.add_tool(new_tool)
        mcp.remove_tool(tool.name)
    else:
        with server_duplicate_behavior(mcp, "replace"):
            mcp.add_tool(new_tool)

if __name__ == "__main__":
    mcp.run(transport="sse", port=mcp_configs.ALL_SERVER_PORTS["gitlab_openapi"])
