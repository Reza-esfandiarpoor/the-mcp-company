import os

os.environ["FASTMCP_EXPERIMENTAL_ENABLE_NEW_OPENAPI_PARSER"] = "true"
##

for k in [
    "MCP_AZURE_VISION_SERVICE",
    "MCP_AZURE_VAULT_NAME",
    "MCP_AZURE_STORAGE_ACCOUNT",
]:
    if os.environ.get(k) is None:
        os.environ[k] = "PLACEHOLDER"

import asyncio
import datetime
import hashlib
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Callable, Dict

import httpx
import requests
import xmltodict
import yaml
from azure.identity.aio import EnvironmentCredential
from fastmcp import Client, FastMCP
from fastmcp.tools import Tool
from fastmcp.tools.tool_transform import ArgTransform, forward_raw
from pydantic import Field
from rich.pretty import pprint

sys.path.append(Path(__file__).parents[1].as_posix())
sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs
import spec_utils

start_time = time.time()

DEFAULT_HTTPX_TIMEOUT = 240  # default timeout for the httpx client


def get_azure_base_url(endpoint_type: str, acct: str | None = None) -> str:
    """Returns the base url for a service.
    For example https://management.azure.com or acctname.table.core.windows.net

    acct is the first part of the url ('acctname' in above example if given).
    It must be provided for endpoints that need it.
    """

    if endpoint_type == "management":
        assert acct is None
        return "https://management.azure.com"
    if endpoint_type == "translator":
        assert acct is None
        return "https://api.cognitive.microsofttranslator.com"

    assert acct is not None

    if endpoint_type == "table":
        return f"https://{acct}.table.core.windows.net"
    elif endpoint_type == "blob":
        return f"https://{acct}.blob.core.windows.net"
    elif endpoint_type == "vision":
        return f"https://{acct}.cognitiveservices.azure.com/vision/v3.2"
    elif endpoint_type == "vault":
        return f"https://{acct}.vault.azure.net"
    else:
        raise ValueError


spec_pardir = Path(__file__).parents[2].joinpath("data/api_specs/azure_v3")

spec_files_to_exclude = [
    "specification/offazurespringboot/resource-manager/Microsoft.OffAzureSpringBoot/preview/2024-04-01-preview/springbootdiscovery.yaml",
    "specification/datafactory/resource-manager/Microsoft.DataFactory/stable/2018-06-01/entityTypes/Pipeline.yaml",
    "specification/cognitiveservices/data-plane/Face/stable/v1.0/Face.yaml",
]

required_spec_files = {
    "vision": [
        "specification/cognitiveservices/data-plane/ComputerVision/stable/v3.2/Ocr.yaml"
    ],
    "data_plane_secrets": [
        "specification/keyvault/data-plane/Microsoft.KeyVault/stable/7.6/secrets.yaml"
    ],
    "data_plane_blob": [
        "specification/storage/data-plane/Microsoft.BlobStorage/stable/2025-11-05/blob.yaml"
    ],
    "data_plane_table": [
        "specification/cosmos-db/data-plane/Microsoft.Tables/preview/2019-02-02/table.yaml"
    ],
    "translate": [
        "specification/cognitiveservices/data-plane/TranslatorText/stable/v3.0/TranslatorText.yaml"
    ],
    "management": [
        "specification/resources/resource-manager/Microsoft.Resources/stable/2025-04-01/resources.yaml",
        "specification/resources/resource-manager/Microsoft.Authorization/stable/2016-09-01/locks.yaml",
        "specification/compute/resource-manager/Microsoft.Compute/ComputeRP/stable/2024-07-01/virtualMachine.yaml",
        "specification/storage/resource-manager/Microsoft.Storage/stable/2019-06-01/blob.yaml",
        "specification/storage/resource-manager/Microsoft.Storage/stable/2019-06-01/storage.yaml",
    ],
}

_all_special_files = []
for special_files in required_spec_files.values():
    for special_file in special_files:
        abs_special = spec_pardir.joinpath(special_file)
        assert abs_special.exists()
        abs_special = abs_special.absolute().resolve().as_posix()
        _all_special_files.append(abs_special)

remaining_files = list()
if os.environ.get("REQUIRED_AZURE_SPECS_ONLY", "false").lower() != "true":
    for file in spec_pardir.rglob("*.yaml"):
        if file.relative_to(spec_pardir).as_posix() in spec_files_to_exclude:
            continue
        abs_p = file.absolute().resolve().as_posix()
        if abs_p not in _all_special_files:
            remaining_files.append(file)
remaining_files = list(sorted(remaining_files, key=lambda p: Path(p).as_posix()))


class AzureCredentialAuth(httpx.Auth):
    """Httpx auth that attaches a fresh AAD bearer token and retries once on 401."""

    requires_request_body = True
    requires_response_body = True

    def __init__(self, credential, scope: str, *, skew_seconds: int = 300):
        self._cred = credential  # e.g., EnvironmentCredential()
        self._scope = scope
        self._skew = skew_seconds  # refresh a little before expiry
        self._token: None = None
        self._lock = asyncio.Lock()  # avoid concurrent refresh storms

    def _is_expiring(self) -> bool:
        return self._token is None or int(time.time()) >= (
            int(self._token.expires_on) - self._skew
        )

    async def _get_token_str(self) -> str:
        async with self._lock:
            if self._is_expiring():
                self._token = await self._cred.get_token(self._scope)
            return self._token.token

    def _apply(self, request: httpx.Request, token: str) -> httpx.Request:
        request.headers["Authorization"] = f"Bearer {token}"
        return request

    # Called by httpx.AsyncClient
    async def async_auth_flow(self, request: httpx.Request):
        # 1st attempt (with current/renewed token)
        token = await self._get_token_str()
        request = self._apply(request, token)
        response = yield request

        # If token was rejected (e.g., just expired), refresh once and retry
        if response.status_code == 401:
            # Force refresh next time
            self._token = None
            token = await self._get_token_str()
            request = self._apply(request, token)
            yield request


##############################################################################
##############################################################################
## Functions that create a wrapper that updates the base url on the fly
##############################################################################
##############################################################################


def make_table_tool_wrapper(parent_tool):
    lock = asyncio.Lock()

    async def with_base_url(
        storage_account: Annotated[
            str, Field(description="The name of the storage account")
        ],
        **kwargs,
    ):
        async with lock:
            orig = parent_tool._client  # private; use carefully
            # new_url = f"https://{storage_account}.table.core.windows.net"
            new_url = get_azure_base_url("table", storage_account)
            tmp = httpx.AsyncClient(
                base_url=new_url,
                headers=getattr(orig, "headers", None),
                timeout=getattr(orig, "timeout", None),
                verify=getattr(orig, "verify", None),
                auth=getattr(orig, "auth", None),
            )
            parent_tool._client = tmp
            try:
                return await forward_raw(**kwargs)
            finally:
                await tmp.aclose()
                parent_tool._client = orig

    return with_base_url


def make_blob_tool_wrapper(parent_tool):
    lock = asyncio.Lock()

    async def with_base_url(
        storage_account: Annotated[
            str, Field(description="The name of the storage account")
        ],
        **kwargs,
    ):
        async with lock:
            orig = parent_tool._client  # private; use carefully
            # new_url = f"https://{storage_account}.blob.core.windows.net"
            new_url = get_azure_base_url("blob", storage_account)
            tmp = httpx.AsyncClient(
                base_url=new_url,
                headers=getattr(orig, "headers", None),
                timeout=getattr(orig, "timeout", None),
                verify=getattr(orig, "verify", None),
                auth=getattr(orig, "auth", None),
            )
            parent_tool._client = tmp
            try:
                return await forward_raw(**kwargs)
            finally:
                await tmp.aclose()
                parent_tool._client = orig

    return with_base_url


def make_vision_tool_wrapper(parent_tool):
    lock = asyncio.Lock()

    async def with_base_url(
        vision_service: Annotated[
            str, Field(description="The name of the vision service location")
        ],
        **kwargs,
    ):
        async with lock:
            orig = parent_tool._client  # private; use carefully
            # new_url = (
            #     f"https://{vision_service}.cognitiveservices.azure.com/vision/v3.2"
            # )
            new_url = get_azure_base_url("vision", vision_service)
            tmp = httpx.AsyncClient(
                base_url=new_url,
                headers=getattr(orig, "headers", None),
                timeout=getattr(orig, "timeout", None),
                verify=getattr(orig, "verify", None),
                auth=getattr(orig, "auth", None),
            )
            parent_tool._client = tmp
            try:
                return await forward_raw(**kwargs)
            finally:
                await tmp.aclose()
                parent_tool._client = orig

    return with_base_url


def make_vault_tool_wrapper(parent_tool):
    lock = asyncio.Lock()

    async def with_base_url(
        vault_name: Annotated[str, Field(description="The name of the vault")], **kwargs
    ):
        async with lock:
            orig = parent_tool._client  # private; use carefully
            # new_url = f"https://{vault_name}.vault.azure.net"
            new_url = get_azure_base_url("vault", vault_name)
            tmp = httpx.AsyncClient(
                base_url=new_url,
                headers=getattr(orig, "headers", None),
                timeout=getattr(orig, "timeout", None),
                verify=getattr(orig, "verify", None),
                auth=getattr(orig, "auth", None),
            )
            parent_tool._client = tmp
            try:
                return await forward_raw(**kwargs)
            finally:
                await tmp.aclose()
                parent_tool._client = orig

    return with_base_url


##############################################################################
##############################################################################
##############################################################################
##############################################################################
##############################################################################

for ch in "0123456789":
    if ch in yaml.SafeLoader.yaml_implicit_resolvers:
        yaml.SafeLoader.yaml_implicit_resolvers[ch] = [
            (tag, regexp)
            for tag, regexp in yaml.SafeLoader.yaml_implicit_resolvers[ch]
            if tag != "tag:yaml.org,2002:timestamp"
        ]


def load_yaml(file: str | Path):
    """Load a yaml file."""
    with open(file, "r") as f:
        obj = yaml.load(f, Loader=yaml.CSafeLoader)
    return obj


@contextmanager
def server_duplicate_behavior(curr_server, new_behavior):
    """Set the duplicate_behavior for FastMCP to 'new_behavior' while inside this context
    manager."""
    old_behavior = curr_server._tool_manager.duplicate_behavior

    curr_server._tool_manager.duplicate_behavior = new_behavior
    try:
        yield
    finally:
        curr_server._tool_manager.duplicate_behavior = old_behavior


async def test_server(
    curr_server: FastMCP,
    call_tool: bool = False,
    tool_name: str | None = None,
    tool_args: Dict | None = None,
    list_tools: bool = False,
    echo_tool_spec: bool = False,
):
    """Test an MCP server by either list the name of its tools, or call a specific tool or both.

    You can do a few things:
        - Call a specific tool: you must set 'call_tool=True', 'tool_name', and 'tool_args'
        - List the name of all tools: set 'list_tools=True'
        - get the specs of a specific tool: set 'echo_tool_spec=True' and 'tool_name'

    This function does not check if the correct combination of arguments is given.
    Make sure you pass the correct set of arguments.

    Examples:
        - asyncio.run(test_server(myserver, list_tools=True))
        - asyncio.run(test_server(myserver, tool_name='get_weather', echo_tool_spec=True))
        - asyncio.run(test_server(myserver, tool_name='get_weather', tool_args={'city': 'seattle'}, call_tool=True))

    Args:
        curr_server: the mcp server you want to test
        call_tool: if True, call a specific tool with the given name and arguments
        tool_name: name of the tool to call or print its specification
        tool_args: arguments of the tool to call
        list_tools: list the name of all tools in this mcp server
    """
    assert list_tools or call_tool or echo_tool_spec

    client = Client(curr_server)
    async with client:
        await client.ping()

        if list_tools or echo_tool_spec:
            tools = await client.list_tools()
            for tool in tools:
                if list_tools:
                    print(tool.name)
                elif echo_tool_spec and tool.name == tool_name:
                    pprint(tool.model_dump())
        elif call_tool:
            res = await client.call_tool(tool_name, tool_args)
            pprint(res)
        else:
            raise ValueError


def add_summary_to_desc(spec: dict) -> dict:
    """Prepends the summary to description for each path in the OpenAPI spec because FastMCP only
    includes the description and not the summary."""
    for k, path_spec in spec["paths"].items():
        for req_type, req_spec in path_spec.items():
            if req_type == "parameters":
                continue
            if "summary" in req_spec or "description" in req_spec:
                sm = req_spec.get("summary", "").strip()
                ds = req_spec.get("description", "").strip()
                new_desc = f"{sm}\n\n{ds}"
                spec["paths"][k][req_type]["description"] = new_desc.strip()
    return spec


def remove_response_schema(spec: dict) -> dict:
    """Remove the response schema to avoid validation errors from FastMCP."""
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


def add_x_ms_paths(spec: dict) -> dict:
    """Adds the content of `x-ms-paths` to `paths`"""
    if "x-ms-paths" in spec:
        for path, path_data in spec["x-ms-paths"].items():
            if path not in spec["paths"]:
                spec["paths"][path] = path_data
        del spec["x-ms-paths"]
    return spec


def spec_processing(spec: dict, filepath: str | Path) -> dict:
    """Run all required processing on the spec file.
    filepath is the path to the file that contains spec.
    It is used to apply some processings conditionally
    """
    extra_proc_files = [
        "WebApps",
        "afdx",
        "azureFirewall",
        "cdn",
        "cdnwebapplicationfirewall",
        "configurationmanager",
        "devcenter",
        "firewallPolicy",
        "maps-management",
        "purviewcatalog",
        "recommendationsservice",
    ]

    spec = add_x_ms_paths(spec)
    spec = add_summary_to_desc(spec)
    spec = remove_response_schema(spec)
    spec_utils.fix_regex_patterns(spec)
    if Path(filepath).stem in extra_proc_files:
        spec = spec_utils.remove_exclusive_minmax_ensure_prop(spec)
    return spec


async def process_tools_for_one_mcp(
    curr_mcp: FastMCP,
    api_version: str,
    tool_prefix: str,
    wrapper_maker: Callable | None = None,
):
    """Set the correct API version for each spec file and also change tool names to be unique.

    Each Azure spec file contains an API version (something like '2024-03-02').
    Two points. First, FastMCP (and probably OpenAPI specs in general) require a numerical version number like '1.0.0'
    Second, this version number is required for most API endpoints as a parameter.
    But, the model that is calling the tool does not know what the API version is.
    So, here is what we do:
        - Before calling this function (even before creating this specific MCP server),
          you should set the version in the api spec file to something acceptable (e.g., '1.0.0')
          And then create the MCP server
        - Then call this function with the resulting MCP server and the original API version.
        - This function goes through the tools in this server and if there is a tool that
          expects an api-version argument, we set its default value to the api version that you pass to this function
          and hide that argument from the model that is calling the tool later.
    Another thing that this function does is to prepend the `tool_prefix` to the name of each
    tool in an effort to make the tool names unique when there are several tools with the same name in different files.

    Args:
        - curr_mcp: MCP server created from one OpenAPI spec file
        - api_version: original api version in the spec yaml file
        - tool_prefix: the prefix to add to tool names (often the file stem)
        - wrapper_make: if given, it calls this function to get a new tool that replaces the logic of the old tool.
            Here, it is mainly used to add the capability to dynamically update the base url.

    Returns:
        Nothing. It changes the mcp server in place.
    """
    all_tools = await curr_mcp.get_tools()
    for tool in all_tools.values():
        params = tool.parameters["properties"]
        transform_args = {}
        for param_name in params.keys():
            if "api" in param_name.lower() and "version" in param_name.lower():
                transform_args[param_name] = ArgTransform(default=str(api_version))
            elif param_name == "x-ms-version":
                transform_args[param_name] = ArgTransform(default=str(api_version))
        new_tool_kwargs = {}
        if len(transform_args):
            new_tool_kwargs["transform_args"] = transform_args
        new_tool_kwargs["name"] = tool_prefix + "_" + tool.name
        if wrapper_maker is not None:
            new_tool_kwargs["transform_fn"] = wrapper_maker(tool)
        new_tool = Tool.from_tool(tool, **new_tool_kwargs)
        curr_mcp.add_tool(new_tool)
        curr_mcp.remove_tool(tool.name)


cred = EnvironmentCredential()

#######################################################################################
## Create the main mcp server
#######################################################################################

mcp = FastMCP("Azure MCP server")

#######################################################################################
## Create tools for any spec file that is not handled separately
#######################################################################################
if len(remaining_files):
    client = httpx.AsyncClient(
        # base_url="https://management.azure.com",
        base_url=get_azure_base_url("management"),
        auth=AzureCredentialAuth(cred, "https://management.azure.com/.default"),
        headers={"Content-Type": "application/json"},
        timeout=DEFAULT_HTTPX_TIMEOUT,
    )

for path in remaining_files:
    spec = load_yaml(path)
    spec = spec_processing(spec, path)
    version = spec["info"]["version"]
    spec["info"]["version"] = "1.0.0"
    if not len(spec["paths"]):
        continue
    curr_mcp = FastMCP.from_openapi(
        openapi_spec=spec, client=client, name=f"{path.stem} MCP Server"
    )
    asyncio.run(
        process_tools_for_one_mcp(
            curr_mcp=curr_mcp, api_version=version, tool_prefix=path.stem
        )
    )
    asyncio.run(mcp.import_server(curr_mcp))

#######################################################################################
## Crate tools for spec files in the management scope that are required
## for solving the tasks
#######################################################################################

spec_rel_paths = required_spec_files["management"]
spec_path_subset = [spec_pardir.joinpath(p) for p in spec_rel_paths]

client = httpx.AsyncClient(
    # base_url="https://management.azure.com",
    base_url=get_azure_base_url("management"),
    auth=AzureCredentialAuth(cred, "https://management.azure.com/.default"),
    headers={"Content-Type": "application/json"},
    timeout=DEFAULT_HTTPX_TIMEOUT,
)

for path in spec_path_subset:
    spec = load_yaml(path)
    spec = spec_processing(spec, path)
    version = spec["info"]["version"]
    spec["info"]["version"] = "1.0.0"
    curr_mcp = FastMCP.from_openapi(
        openapi_spec=spec, client=client, name=f"{path.stem} MCP Server"
    )
    asyncio.run(
        process_tools_for_one_mcp(
            curr_mcp=curr_mcp, api_version=version, tool_prefix=path.stem
        )
    )
    asyncio.run(mcp.import_server(curr_mcp))

#######################################################################################
## First mini mcp server
## MCP server for the subset of files that share a base url and request headers
## For example all vision understanding endpoints that require the following
## base url for the host:
## https://txtfromimagevis.cognitiveservices.azure.com/vision/v3.2
#######################################################################################
# specify the spec files that need to use this client
spec_rel_paths = required_spec_files["vision"]
spec_path_subset = [spec_pardir.joinpath(p) for p in spec_rel_paths]

# get the token for this client/group of endpoints
ocr_client = httpx.AsyncClient(
    # base_url=f"https://{os.environ['MCP_AZURE_VISION_SERVICE']}.cognitiveservices.azure.com/vision/v3.2",
    base_url=get_azure_base_url("vision", os.environ["MCP_AZURE_VISION_SERVICE"]),
    auth=AzureCredentialAuth(cred, "https://cognitiveservices.azure.com/.default"),
    headers={"Content-Type": "application/json"},
    timeout=DEFAULT_HTTPX_TIMEOUT,
)
for spec_path in spec_path_subset:
    spec = load_yaml(spec_path)
    spec = spec_processing(spec, spec_path)
    # keep the original version to use it as argument
    version = spec["info"]["version"]
    # fastmcp only accepts versions like '1.0.0' and not '2024-02-03' that is in the original spec files
    spec["info"]["version"] = "1.0.0"
    curr_mcp = FastMCP.from_openapi(
        openapi_spec=spec, client=ocr_client, name=f"{spec_path.stem} MCP Server"
    )
    asyncio.run(
        process_tools_for_one_mcp(
            curr_mcp=curr_mcp,
            api_version=version,
            tool_prefix=spec_path.stem,
            wrapper_maker=make_vision_tool_wrapper,
        )
    )
    # import all tools from this mcp server to the main Azure mcp server
    asyncio.run(mcp.import_server(curr_mcp))


@mcp.tool
async def Ocr_Read(
    vision_service: Annotated[
        str, Field(description="the name of the vision service location.")
    ],
    url: Annotated[
        str, Field(description="Publicly accessible url of the content to be analyzed.")
    ],
):
    """Use this interface to get the result of a Read operation, employing the state-of-the-art
    Optical Character Recognition (OCR) algorithms optimized for text-heavy documents.
    """
    _token = await EnvironmentCredential().get_token(
        "https://cognitiveservices.azure.com/.default"
    )
    token = _token.token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    vision_endpoint = (
        f"https://{vision_service}.cognitiveservices.azure.com/vision/v3.2/read/analyze"
    )
    body = {"url": url}

    response = requests.post(vision_endpoint, headers=headers, json=body)
    response.raise_for_status()

    # Get operation location for polling
    operation_url = response.headers["Operation-Location"]

    # Step 3: Poll until OCR is done
    while True:
        result = requests.get(
            operation_url, headers={"Authorization": f"Bearer {token}"}
        ).json()
        if result["status"] in ["succeeded", "failed"]:
            break
        time.sleep(1)

    if result["status"] != "succeeded":
        raise Exception(f"OCR failed: {result}")

    # Step 4: Extract text
    lines = []
    for page in result["analyzeResult"]["readResults"]:
        for line in page["lines"]:
            lines.append(line["text"])
    lines = "\n".join(lines)
    return lines


# tool = asyncio.run(mcp.get_tool("Ocr_Read"))
# new_tool = Tool.from_tool(tool, transform_fn=Ocr_Read)
# mcp.add_tool(new_tool)

#######################################################################################
## MCP server for the subset of files for 'https://{vault_name}.vault.azure.net'
#######################################################################################
# specify the spec files that need to use this client
spec_rel_paths = required_spec_files["data_plane_secrets"]
spec_path_subset = [spec_pardir.joinpath(p) for p in spec_rel_paths]

# get the token for this client/group of endpoints
client = httpx.AsyncClient(
    # base_url=f"https://{os.environ['MCP_AZURE_VAULT_NAME']}.vault.azure.net",
    base_url=get_azure_base_url("vault", os.environ["MCP_AZURE_VAULT_NAME"]),
    auth=AzureCredentialAuth(cred, "https://vault.azure.net/.default"),
    timeout=DEFAULT_HTTPX_TIMEOUT,
)
for spec_path in spec_path_subset:
    spec = load_yaml(spec_path)
    spec = spec_processing(spec, spec_path)
    # keep the original version to use it as argument
    version = spec["info"]["version"]
    # fastmcp only accepts versions like '1.0.0' and not '2024-02-03' that is in the original spec files
    spec["info"]["version"] = "1.0.0"
    curr_mcp = FastMCP.from_openapi(
        openapi_spec=spec, client=client, name=f"{spec_path.stem} MCP Server"
    )
    asyncio.run(
        process_tools_for_one_mcp(
            curr_mcp=curr_mcp,
            api_version=version,
            tool_prefix=spec_path.stem,
            wrapper_maker=make_vault_tool_wrapper,
        )
    )
    # import all tools from this mcp server to the main Azure mcp server
    asyncio.run(mcp.import_server(curr_mcp))

#######################################################################################
## MCP server for the subset of files for 'https://{storage_acct}.blob.core.windows.net'
#######################################################################################
# specify the spec files that need to use this client
spec_rel_paths = required_spec_files["data_plane_blob"]
spec_path_subset = [spec_pardir.joinpath(p) for p in spec_rel_paths]

# get the token for this client/group of endpoints
headers = {"x-ms-blob-type": "BlockBlob"}
client = httpx.AsyncClient(
    # base_url=f"https://{os.environ['MCP_AZURE_STORAGE_ACCOUNT']}.blob.core.windows.net",
    base_url=get_azure_base_url("blob", os.environ["MCP_AZURE_STORAGE_ACCOUNT"]),
    auth=AzureCredentialAuth(cred, "https://storage.azure.com/.default"),
    headers=headers,
    timeout=DEFAULT_HTTPX_TIMEOUT,
)
for spec_path in spec_path_subset:
    spec = load_yaml(spec_path)
    spec = spec_processing(spec, spec_path)
    # keep the original version to use it as argument
    version = spec["info"]["version"]
    # fastmcp only accepts versions like '1.0.0' and not '2024-02-03' that is in the original spec files
    spec["info"]["version"] = "1.0.0"
    curr_mcp = FastMCP.from_openapi(
        openapi_spec=spec, client=client, name=f"{spec_path.stem} MCP Server"
    )
    asyncio.run(
        process_tools_for_one_mcp(
            curr_mcp=curr_mcp,
            api_version=version,
            tool_prefix=spec_path.stem,
            wrapper_maker=make_blob_tool_wrapper,
        )
    )
    # import all tools from this mcp server to the main Azure mcp server
    asyncio.run(mcp.import_server(curr_mcp))


def get_x_ms_date() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")


async def enable_static_website_data_plane(**kwargs):
    token = await cred.get_token("https://storage.azure.com/.default")
    token = token.token
    headers = {
        "Authorization": f"Bearer {token}",
        "x-ms-version": "2025-07-05",
        "x-ms-date": get_x_ms_date(),
        "Content-Type": "application/xml",
    }
    url = f"https://{kwargs['storage_account']}.blob.core.windows.net/?restype=service&comp=properties"
    body = {}
    for k in ["Cors", "HourMetrics", "Logging", "MinuteMetrics", "StaticWebsite"]:
        if k in kwargs:
            body[k] = kwargs.pop(k)
    xml_body = xmltodict.unparse({"StorageServiceProperties": body}, pretty=True)

    resp = requests.put(url, headers=headers, data=xml_body)
    resp.raise_for_status()
    return resp.content


if len(spec_path_subset):
    old_tool = asyncio.run(mcp.get_tool("blob_Service_SetProperties"))
    new_tool = Tool.from_tool(old_tool, transform_fn=enable_static_website_data_plane)
    mcp.add_tool(new_tool)


@mcp.tool
async def blob_BlockBlob_Upload(
    storage_account: Annotated[
        str, Field(description="the name of the storage account.")
    ],
    container_name: Annotated[
        str, Field(description="The name of the container to store blob to")
    ],
    blob_name: Annotated[
        str, Field(description="the name of the blob to upload the data to")
    ],
    data: Annotated[str, Field(description="The text content to upload to the blob")],
):
    """Updating an existing block blob overwrites any existing metadata on the blob.

    Partial updates are not supported with Put Blob; the content of the existing blob is
    overwritten with the content of the new blob. To perform a partial update of the content of a
    block blob, use the Put Block List operation.
    """

    token = await cred.get_token("https://storage.azure.com/.default")
    token = token.token
    # Blob URL
    blob_url = (
        f"https://{storage_account}.blob.core.windows.net/{container_name}/{blob_name}"
    )

    # Upload the text using REST API
    headers = {
        "Authorization": f"Bearer {token}",
        "x-ms-blob-type": "BlockBlob",
        "x-ms-version": "2021-08-06",
        "Content-Type": "text/plain",
    }

    response = requests.put(blob_url, headers=headers, data=data.encode("utf-8"))
    response.raise_for_status()


#######################################################################################
## MCP server for the subset of files for 'https://{storage_acct}.table.core.windows.net'
#######################################################################################
# specify the spec files that need to use this client
spec_rel_paths = required_spec_files["data_plane_table"]
spec_path_subset = [spec_pardir.joinpath(p) for p in spec_rel_paths]

# get the token for this client/group of endpoints
headers = {
    "x-ms-date": get_x_ms_date(),
    "x-ms-version": "2019-02-02",
    "Accept": "application/json;odata=nometadata",
}
client = httpx.AsyncClient(
    # base_url=f"https://{os.environ['MCP_AZURE_STORAGE_ACCOUNT']}.table.core.windows.net",
    base_url=get_azure_base_url("table", os.environ["MCP_AZURE_STORAGE_ACCOUNT"]),
    auth=AzureCredentialAuth(cred, "https://storage.azure.com/.default"),
    headers=headers,
    timeout=DEFAULT_HTTPX_TIMEOUT,
)
for spec_path in spec_path_subset:
    spec = load_yaml(spec_path)
    spec = spec_processing(spec, spec_path)
    # keep the original version to use it as argument
    version = spec["info"]["version"]
    # fastmcp only accepts versions like '1.0.0' and not '2024-02-03' that is in the original spec files
    spec["info"]["version"] = "1.0.0"
    curr_mcp = FastMCP.from_openapi(
        openapi_spec=spec, client=client, name=f"{spec_path.stem} MCP Server"
    )
    asyncio.run(
        process_tools_for_one_mcp(
            curr_mcp=curr_mcp,
            api_version=version,
            tool_prefix=spec_path.stem,
            wrapper_maker=make_table_tool_wrapper,
        )
    )
    # import all tools from this mcp server to the main Azure mcp server
    asyncio.run(mcp.import_server(curr_mcp))


@mcp.tool
async def table_Table_InsertEntity(
    storage_account: Annotated[
        str, Field(description="the name of the storage account.")
    ],
    table_name: Annotated[str, Field(description="the name of the target.")],
    data: Annotated[
        dict,
        Field(
            description="the data record to insert into the table. It should be a dictionary of key values."
        ),
    ],
):

    token = await cred.get_token("https://storage.azure.com/.default")
    token = token.token

    url = f"https://{storage_account}.table.core.windows.net/{table_name}"
    headers = {
        "x-ms-date": get_x_ms_date(),
        "x-ms-version": "2019-02-02",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json;odata=nometadata",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code in (201, 204):
        return "Entity inserted successfully"


#######################################################################################
## MCP server for the subset of files for 'https://api.cognitive.microsofttranslator.com'
#######################################################################################
# specify the spec files that need to use this client
spec_rel_paths = required_spec_files["translate"]
spec_path_subset = [spec_pardir.joinpath(p) for p in spec_rel_paths]

# get the token for this client/group of endpoints
headers = {
    "Content-Type": "application/json",
    "Ocp-Apim-Subscription-Region": "eastus",
}
client = httpx.AsyncClient(
    # base_url=f"https://api.cognitive.microsofttranslator.com",
    base_url=get_azure_base_url("translator"),
    auth=AzureCredentialAuth(cred, "https://cognitiveservices.azure.com/.default"),
    headers=headers,
    timeout=DEFAULT_HTTPX_TIMEOUT,
)
for spec_path in spec_path_subset:
    spec = load_yaml(spec_path)
    spec = spec_processing(spec, spec_path)
    # keep the original version to use it as argument
    version = spec["info"]["version"]
    # fastmcp only accepts versions like '1.0.0' and not '2024-02-03' that is in the original spec files
    spec["info"]["version"] = "1.0.0"
    curr_mcp = FastMCP.from_openapi(
        openapi_spec=spec, client=client, name=f"{spec_path.stem} MCP Server"
    )
    asyncio.run(
        process_tools_for_one_mcp(
            curr_mcp=curr_mcp,
            api_version=version,
            tool_prefix=spec_path.stem,
        )
    )
    # import all tools from this mcp server to the main Azure mcp server
    asyncio.run(mcp.import_server(curr_mcp))


@mcp.tool
async def TranslatorText_Translator_Translate(
    subscription_id: Annotated[str, Field(description="Subscription ID for Azure")],
    resource_group: Annotated[
        str, Field(description="Resource group that contains the translation service")
    ],
    account_name: Annotated[
        str,
        Field(description="Cognitive services account for Azure translation service"),
    ],
    source_language: Annotated[
        str, Field(description="Language code of the source document (e.g., de)")
    ],
    target_language: Annotated[
        str,
        Field(
            description="Language code of the target language to translate the document into (e.g., de)"
        ),
    ],
    text: Annotated[str, Field(description="The text to be translated")],
):
    """Translates text into one or more languages."""
    token = await cred.get_token("https://cognitiveservices.azure.com/.default")
    token = token.token

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Region": "eastus",
        "Ocp-Apim-ResourceId": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices/accounts/{account_name}",
    }
    endpoint = "https://api.cognitive.microsofttranslator.com"

    url = (
        endpoint
        + f"/translate?api-version=3.0&from={source_language}&to={target_language}"
    )

    # Text to translate
    body = [{"Text": text}]
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    result = response.json()
    result = result[0]["translations"][0]["text"]
    return result


@mcp.tool
async def TranslatorText_Translator_Detect(
    subscription_id: Annotated[str, Field(description="Subscription ID for Azure")],
    resource_group: Annotated[
        str, Field(description="Resource group that contains the translation service")
    ],
    account_name: Annotated[
        str,
        Field(description="Cognitive services account for Azure translation service"),
    ],
    text: Annotated[str, Field(description="The text to detect its language")],
):
    """Identifies the language of a string of text."""
    token = await cred.get_token("https://cognitiveservices.azure.com/.default")
    token = token.token

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Region": "eastus",
        # anthaue TODO: construct this by passing the sub id and res id in here.
        "Ocp-Apim-ResourceId": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices/accounts/{account_name}",
    }

    endpoint = "https://api.cognitive.microsofttranslator.com"
    url = endpoint + f"/detect?api-version=3.0"

    # Text to detect
    body = [{"Text": text}]
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    result = response.json()
    return result[0]["language"]


#######################################################################################
## Process all tools in the mcp server
#######################################################################################
# this loop makes sure the name of tools is at most 64 characters
# if it is more than 64 characters, it just adds a unique hash to the begining and truncates the begining of the name
all_tools = asyncio.run(mcp.get_tools())
for tool in all_tools.values():
    if (
        len(tool.name) >= 58
    ):  # we check for 58 since later 'azure_' is added to the name of all tools, when the model sees them
        name_hash = hashlib.sha256(tool.name.encode()).hexdigest()[:4]
        new_name = name_hash + tool.name[-46:]
        new_tool = Tool.from_tool(tool, name=new_name)
        mcp.add_tool(new_tool)
        # don't forget to remove the old tool
        # When the name of the tool changes, the old one is not replaced automatically
        mcp.remove_tool(tool.name)

#######################################################################################
print(f"Total number of Azure tools: {len(all_tools)}")
print("Elapsed time:", str(datetime.timedelta(seconds=time.time() - start_time)))
if __name__ == "__main__":
    mcp.run(transport="sse", port=mcp_configs.ALL_SERVER_PORTS["azure"])
