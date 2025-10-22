import os
import sys
import time
from pathlib import Path

import requests

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
from azure_mcp_ops import call_mcp_tool_parse

mcp_url = os.environ.get("AZTASK_MCP_SERVER_URL", "http://localhost:51468/sse")

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]

####################
####################
####################

print("> Find Cosmosdb account name")
resp = call_mcp_tool_parse(
    mcp_url,
    "cosmos-db_DatabaseAccounts_List",
    {"subscriptionId": sub_id},
)
db_acct_list = list()
for item in resp["value"]:
    if item["type"] == "Microsoft.DocumentDB/databaseAccounts":
        db_acct = item["name"]
        db_loc = item["location"]
        rg = item["id"].split("/")[4]
        db_acct_list.append(dict(acct=db_acct, loc=db_loc, rg=rg))
        print(db_acct_list[-1])

print("> Disable key-based Auth for Cosmosdb")
for dba in db_acct_list:
    resp = call_mcp_tool_parse(
        mcp_url,
        "cosmos-db_DatabaseAccounts_Update",
        {
            "subscriptionId": sub_id,
            "resourceGroupName": dba["rg"],
            "accountName": dba["acct"],
            "location": dba["loc"],
            "properties": {"properties": {"disableLocalAuth": True}},
        },
    )


print("> List resources to find apps related to cosmosdb")
resp = call_mcp_tool_parse(
    mcp_url, "resources_Resources_List", {"subscriptionId": sub_id}
)
webapp_name = None
for item in resp["value"]:
    if (
        "cosmos" in item["name"]
        and item["type"] != "Microsoft.DocumentDB/databaseAccounts"
    ):
        webapp_name = item["name"]
        webapp_rg = item["id"].split("/")[4]
        print(f"name: {webapp_name}")
        print(f"rg: {webapp_rg}")
assert webapp_name is not None


print(f"> Get Kudus credentials")
resp = call_mcp_tool_parse(
    mcp_url,
    "WebApps_WebApps_ListPublishingCredentials",
    {"subscriptionId": sub_id, "resourceGroupName": webapp_rg, "name": webapp_name},
)
pub_user = resp["properties"]["publishingUserName"]
pub_pass = resp["properties"]["publishingPassword"]
auth = (pub_user, pub_pass)
scm_uri = resp["properties"]["scmUri"]
scm_uri = "https://" + scm_uri.split("@")[-1]

print(f"> List all files for the web app")
creds = {"properties": {"publishingUserName": pub_user, "publishingPassword": pub_pass}}
vfs_url = f"{scm_uri}/api/vfs/site/wwwroot/"
resp = requests.get(vfs_url, auth=auth)
# now the agent knows that one of them is a directory and it has to traverse it
resp = resp.json()

vfs_url = f"{scm_uri}/api/vfs/site/wwwroot/TestDbAccess"
resp = requests.get(vfs_url, auth=auth)
# It has found the only python file and now it should read its content
resp = resp.json()

vfs_url = f"{scm_uri}/api/vfs/site/wwwroot/TestDbAccess/__init__.py"
resp = requests.get(vfs_url, auth=auth)
old_file_content = resp.text
# now the agent sees the error
print("Old file content head")
print("\n".join(old_file_content.split("\n")[:5]))

print("> Write the updated file content")
with open(Path(__file__).parent / "access_cosmosdb_rbac.py", "r") as file:
    new_file_content = file.read()
vfs_url = f"{scm_uri}/api/vfs/site/wwwroot/TestDbAccess/__init__.py"
vfs_headers = {
    "Content-Type": "text/plain",
    "If-Match": "*",  # Overwrite if exists
}
write_response = requests.put(
    vfs_url, auth=auth, headers=vfs_headers, data=new_file_content
)
write_response.raise_for_status()

print(f"> Stop web app")
resp = call_mcp_tool_parse(
    mcp_url,
    "WebApps_WebApps_Stop",
    {"subscriptionId": sub_id, "resourceGroupName": webapp_rg, "name": webapp_name},
)
print("Wait for the app to stop")
time.sleep(60)

print(f"> Start web app")
resp = call_mcp_tool_parse(
    mcp_url,
    "WebApps_WebApps_Start",
    {"subscriptionId": sub_id, "resourceGroupName": webapp_rg, "name": webapp_name},
)
