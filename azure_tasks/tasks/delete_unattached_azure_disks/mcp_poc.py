import json
import os
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

####


sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg_name = "azuretasks_delete_unattached_disks"

vms = azure_mcp_ops.list_vms_in_rg(sub_id=sub_id, rg_name=rg_name)

attached_disks = []
for vm in vms:
    vm_name = vm["name"]
    location = vm["location"]
    os_disk = vm["properties"]["storageProfile"]["osDisk"]
    attached_disks.append(os_disk["managedDisk"]["id"].lower())
    data_disks = vm["properties"]["storageProfile"].get("dataDisks", [])

    print(f"VM: {vm_name} ({location})")
    for d in data_disks:
        attached_disks.append(d["managedDisk"]["id"].lower())

all_res = azure_mcp_ops.list_resources_in_rg(sub_id=sub_id, rg_name=rg_name)

all_disks = []
for r in all_res:
    if r["type"] == "Microsoft.Compute/disks":
        all_disks.append(r["id"])

print("all disks")
print(all_disks)

print()

print("attached disks")
print(attached_disks)

print("Unattached")
for dsk in all_disks:
    if dsk.lower() not in attached_disks:
        print("deleting")
        print(dsk)
        azure_mcp_ops.delete_resource(
            sub_id=sub_id,
            rg_name=rg_name,
            resource_provider_namespace="Microsoft.Compute",
            resource_type="disks",
            parent_resource="",
            resource_name=dsk.strip("/").split("/")[-1],
            api_v="2025-01-02",
        )
