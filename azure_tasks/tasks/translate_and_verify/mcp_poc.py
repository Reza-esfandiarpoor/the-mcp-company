import json
import os
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_mcp_ops

####


sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
exp_uuid = os.environ["EXP_UUID"]
acct_name = f"trname{exp_uuid}"
resource_group = "azuretasks_translate_and_verify"
endpoint = "https://api.cognitive.microsofttranslator.com"

storage_acct = f"sacct{exp_uuid}"
storage_ctr = "translatenverifyctr"

german_text = azure_mcp_ops.read_from_blob(storage_acct, storage_ctr, "original.txt")
print("Original Text")
print(german_text)
english_text = azure_mcp_ops.translate_text(
    sub_id, resource_group, acct_name, "de", "en", german_text
)
print("Translated Text")
print(english_text)

detected = azure_mcp_ops.detect_lang(sub_id, resource_group, acct_name, english_text)

azure_mcp_ops.write_to_blob(storage_acct, storage_ctr, "result.txt", english_text)
azure_mcp_ops.write_to_blob(storage_acct, storage_ctr, "text.langid", detected)
