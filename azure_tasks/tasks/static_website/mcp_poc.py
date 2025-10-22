import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
exp_uuid = os.environ["EXP_UUID"]

storage_acct = f"sacct{exp_uuid}"
resource_group = "azuretasks_static_website"

azure_mcp_ops.ensure_blob_service(sub_id, resource_group, storage_acct, "default", {})
azure_mcp_ops.enable_static_website_data_plane(storage_acct)

azure_mcp_ops.create_container(storage_acct, "$web")

azure_mcp_ops.write_to_blob(
    storage_acct,
    "$web",
    "index.html",
    "<HTML><HEAD></HEAD><BODY><P>Capybaras are great</P></BODY></HTML>",
)

azure_mcp_ops.write_to_blob(
    storage_acct,
    "$web",
    "404.html",
    "<HTML><HEAD></HEAD><BODY><P>Sorry, no Capybaras found here.</P></BODY></HTML>",
)
