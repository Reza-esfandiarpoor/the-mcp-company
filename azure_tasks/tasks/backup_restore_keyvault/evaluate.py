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

kvfrom = f"kvfrom{exp_uuid}"
kvto = f"kvto{exp_uuid}"

secrets = azure_ops.list_kv_secrets(kvto)

score = 0
for secret in secrets:
    print(secret)
    if "mysecret" in secret["id"]:
        score = 1
        break
checkpoints = [{"total": 1, "result": score}]

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
