import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

####


sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg_name = "azuretasks_delete_test_vms"

res = azure_mcp_ops.list_resources_in_rg(rg_name=rg_name, sub_id=sub_id)

deleteme = []
for r in res:
    resid = r["id"]
    name = r["name"]
    print(f"Checking resource {name}")
    if r["type"] == "Microsoft.Compute/virtualMachines":
        isTest = False
        if "test" in r["name"]:
            isTest = True
            deleteme.append(resid)
            continue
        for t in r["tags"]:
            if "test" in t or "test" in r["tags"][t]:
                isTest = True
                deleteme.append(resid)
                continue

for d in deleteme:
    print("deleting")
    print(d)
    azure_mcp_ops.delete_resource(
        sub_id=sub_id,
        rg_name=rg_name,
        resource_provider_namespace="Microsoft.Compute",
        resource_type="virtualMachines",
        resource_name=d.strip("/").split("/")[-1],
        parent_resource="",
    )
