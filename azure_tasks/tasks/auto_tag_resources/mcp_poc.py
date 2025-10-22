import json
import os
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

mcp_url = os.environ["AZTASK_MCP_SERVER_URL"]

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg_name = "azuretasks_auto_tag_resources"

res = azure_mcp_ops.list_resources_in_rg(rg_name=rg_name, sub_id=sub_id)

restype2tag = {"Microsoft.KeyVault/vaults": "Security"}

for r in res:
    name = r["name"]
    print(f"Checking resource {name}\n")
    if r["type"] in restype2tag:
        want_tag = restype2tag[r["type"]]
        if "Category" in r["tags"] and r["tags"]["Category"] == want_tag:
            print("Already good\n")
        else:
            sys.stderr.write(f"Tagging with {want_tag}")
            call_mcp_tool(
                mcp_url,
                "resources_Tags_UpdateAtScope",
                args={
                    "scope": r["id"],
                    "operation": "Merge",
                    "properties": {"tags": {f"Category": f"{want_tag}"}},
                },
            )
    else:
        print("Skipping, resource type not defined")
