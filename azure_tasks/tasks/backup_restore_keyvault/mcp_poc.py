import os
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

mcp_url = os.environ["AZTASK_MCP_SERVER_URL"]

####


def secret_name_from_secret(get_from_me: str) -> str:
    return get_from_me.split("/")[-1]


sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
exp_uuid = os.environ["EXP_UUID"]

kvfrom = f"kvfrom{exp_uuid}"
kvto = f"kvto{exp_uuid}"

all_secrets = azure_mcp_ops.list_kv_secrets(kvfrom)

for secret in all_secrets:
    secname = secret_name_from_secret(secret["id"])
    secval = azure_mcp_ops.backup_kv_secret(kv_name=kvfrom, sename=secname)
    azure_mcp_ops.restore_secret(kvname=kvto, value=secval)
