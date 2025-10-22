import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

mcp_url = os.environ["AZTASK_MCP_SERVER_URL"]

####


def secret_name_from_secret(get_from_me: str) -> str:
    return get_from_me.split("/")[-1]


exp_uuid = os.environ["EXP_UUID"]

kv_name = f"kvlt{exp_uuid}"
storage_acct = f"sact{exp_uuid}"
container_name = "azuretasks-kv-read-backup"

azure_mcp_ops.create_container(storage_acct=storage_acct, container_name=container_name)
secrets = azure_mcp_ops.list_kv_secrets(kv_name)

for secret in secrets:
    secname = secret_name_from_secret(secret["id"])
    secval = azure_mcp_ops.backup_kv_secret(kv_name=kv_name, secname=secname)
    azure_mcp_ops.write_to_blob(
        storage_acct=storage_acct,
        container_name=container_name,
        blob_name=secname,
        data=secval,
    )
