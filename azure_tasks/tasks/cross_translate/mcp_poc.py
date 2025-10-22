import os
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

mcp_url = os.environ["AZTASK_MCP_SERVER_URL"]

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
exp_uuid = os.environ["EXP_UUID"]
resource_group = "azuretasks_cross_translate"
acct_name = f"trname{exp_uuid}"

endpoint = "https://api.cognitive.microsofttranslator.com"
storage_acct = f"sacct{exp_uuid}"


unsorted_ctr = "sort-me"
orig_en_ctr = "orig-en"
orig_fa_ctr = "orig-fa"
orig_other_ctr = "orig-other"
en_to_fa_ctr = "en-to-fa"
fa_to_en_ctr = "fa-to-en"

azure_mcp_ops.create_container(storage_acct, orig_en_ctr)
azure_mcp_ops.create_container(storage_acct, orig_fa_ctr)
azure_mcp_ops.create_container(storage_acct, orig_other_ctr)
azure_mcp_ops.create_container(storage_acct, en_to_fa_ctr)
azure_mcp_ops.create_container(storage_acct, fa_to_en_ctr)

orig_blobs = azure_mcp_ops.list_blobs(
    storage_acct=storage_acct, container_name=unsorted_ctr
)

for blobname in orig_blobs:
    txt = azure_mcp_ops.read_from_blob(
        storage_acct=storage_acct, blob_name=blobname, container_name=unsorted_ctr
    )
    lang = azure_mcp_ops.detect_lang(
        sub_id=sub_id, rg_name=resource_group, account_name=acct_name, text=txt
    )

    if lang == "en":
        azure_mcp_ops.write_to_blob(storage_acct, orig_en_ctr, blobname, txt)
        xlated = azure_mcp_ops.translate_text(
            sub_id,
            resource_group,
            translator_acct=acct_name,
            src_lang="en",
            dst_lang="fa",
            text=txt,
        )
        azure_mcp_ops.write_to_blob(storage_acct, en_to_fa_ctr, blobname, xlated)
    elif lang == "fa":
        azure_mcp_ops.write_to_blob(storage_acct, orig_fa_ctr, blobname, txt)
        xlated = azure_mcp_ops.translate_text(
            sub_id,
            resource_group,
            translator_acct=acct_name,
            src_lang="fa",
            dst_lang="en",
            text=txt,
        )
        azure_mcp_ops.write_to_blob(storage_acct, fa_to_en_ctr, blobname, xlated)
    else:
        azure_mcp_ops.write_to_blob(storage_acct, orig_other_ctr, blobname, txt)
