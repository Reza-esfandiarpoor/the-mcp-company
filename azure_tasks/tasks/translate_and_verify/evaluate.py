import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
exp_uuid = os.environ["EXP_UUID"]
acct_name = f"trname{exp_uuid}"
resource_group = "azuretasks_translate_and_verify"
endpoint = "https://api.cognitive.microsofttranslator.com"

storage_acct = f"sacct{exp_uuid}"
storage_ctr = "translatenverifyctr"


checkpoints = []


def ckpt(s):
    checkpoints.append({"total": 1, "result": s})


if azure_ops.blob_exists(storage_acct, storage_ctr, "result.txt"):
    ckpt(1)
    translated = azure_ops.read_text_from_blob(storage_acct, storage_ctr, "result.txt")
    translated = translated.lower()
    if "crab" in translated:
        ckpt(1)
    else:
        ckpt(0)
else:
    ckpt(0)
    ckpt(0)

if azure_ops.blob_exists(storage_acct, storage_ctr, "text.langid"):
    ckpt(1)
    detected = azure_ops.read_text_from_blob(storage_acct, storage_ctr, "text.langid")
    if "en" in detected:
        ckpt(1)
    else:
        ckpt(0)
else:
    ckpt(0)
    ckpt(0)


output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
