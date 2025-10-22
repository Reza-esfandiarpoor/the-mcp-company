import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
exp_uuid = os.environ["EXP_UUID"]
rg_name = "azuretasks_delete_locked_resource"
kv_name = f"mykv{exp_uuid}"

resources = azure_mcp_ops.list_resources_in_rg(sub_id=sub_id, rg_name=rg_name)


locks = azure_mcp_ops.list_kv_locks(sub_id, rg_name, kv_name)

for lock in locks:
    s = lock["id"]
    azure_mcp_ops.delete_resource(
        sub_id=sub_id,
        rg_name=rg_name,
        resource_provider_namespace=s.split("/")[6],
        parent_resource="/".join(s.split("/")[7:11]),
        resource_type="locks",
        resource_name=s.split("/").strip("/")[-1],
        api_v="2020-05-01",
    )

for res in resources:
    if res["name"] == kv_name:
        azure_mcp_ops.delete_resource(
            sub_id=sub_id,
            rg_name=rg_name,
            resource_provider_namespace="Microsoft.KeyVault",
            resource_type="vaults",
            resource_name=res["id"].strip("/").split("/")[-1],
            parent_resource="",
            api_v="2023-07-01",
        )
