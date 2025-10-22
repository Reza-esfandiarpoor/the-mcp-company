import os
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
from azure_mcp_ops import call_mcp_tool_parse

mcp_url = os.environ.get("AZTASK_MCP_SERVER_URL", "http://localhost:51468/sse")

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg_name = "rg-poppy"

###
print("> Find api web app name")
all_resources = call_mcp_tool_parse(
    url=mcp_url,
    name="resources_Resources_ListByResourceGroup",
    args={"resourceGroupName": rg_name, "subscriptionId": sub_id},
)
all_resources = all_resources["value"]

api_app_name = None
for rs in all_resources:
    if rs["type"] == "Microsoft.Web/sites" and "api" in rs["name"]:
        api_app_name = rs["name"]
        print(f"Web app resource name: {api_app_name}")
assert api_app_name is not None


print("> Check if the web app is a container")
resp = call_mcp_tool_parse(
    mcp_url,
    "WebApps_WebApps_GetConfiguration",
    {"name": api_app_name, "resourceGroupName": rg_name, "subscriptionId": sub_id},
)
lfxv = resp["properties"]["linuxFxVersion"]
if lfxv.split("|")[0].isupper():
    print("it is a container")


print("> Get the web app container logs")
log_text = call_mcp_tool_parse(
    mcp_url,
    "WebApps_WebApps_GetWebSiteContainerLogs",
    {"resourceGroupName": rg_name, "name": api_app_name, "subscriptionId": sub_id},
)
if "mongo" in log_text:
    print("the problem is with mongodb version")

print("> Find Cosmosdb account name")
resp = call_mcp_tool_parse(
    mcp_url,
    "cosmos-db_DatabaseAccounts_ListByResourceGroup",
    {"subscriptionId": sub_id, "resourceGroupName": rg_name},
)
db_acct = None
for item in resp["value"]:
    if item["name"].endswith(api_app_name.split("-")[-1].strip()):
        db_acct = item["name"]
        print(f"Database account: {db_acct}")
assert db_acct is not None

print("> find the current configured mongodb api server version")
resp = call_mcp_tool_parse(
    mcp_url,
    "cosmos-db_DatabaseAccounts_Get",
    {"subscriptionId": sub_id, "resourceGroupName": rg_name, "accountName": db_acct},
)
server_version = resp["properties"]["apiProperties"]["serverVersion"]
print("db api server version:", server_version)


print("> change the api version to correct value")
resp = call_mcp_tool_parse(
    mcp_url,
    "cosmos-db_DatabaseAccounts_Update",
    {
        "subscriptionId": sub_id,
        "resourceGroupName": rg_name,
        "accountName": db_acct,
        "properties": {"apiProperties": {"serverVersion": "4.2"}},
    },
)

print("> Restart the api web app")
resp = call_mcp_tool_parse(
    mcp_url,
    "WebApps_WebApps_Restart",
    {
        "resourceGroupName": rg_name,
        "name": api_app_name,
        "subscriptionId": sub_id,
    },
)

print("App restarted")
