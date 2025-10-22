import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####


exp_uuid = os.environ["EXP_UUID"]
storage_acct = f"sacct{exp_uuid}"
container_name = "txtfromimagectr"


label_txt = "writing things on the wal"

checkpoints = []


def ckpt(s):
    checkpoints.append({"total": 1, "result": s})


if azure_ops.blob_exists(storage_acct, container_name, "result.txt"):
    ckpt(1)
    result = azure_ops.read_text_from_blob(storage_acct, container_name, "result.txt")
    result = result.strip().lower()
    if label_txt.strip().lower() in result.lower():
        ckpt(1)
    else:
        ckpt(0)
else:
    ckpt(0)
    ckpt(0)


output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
