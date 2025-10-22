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
kv_name = f"mykv{exp_uuid}"
rg_name = "azuretasks_delete_locked_resource"

resources = azure_ops.list_resources_in_rg(
    subscription_id=sub_id, resource_group=rg_name
)
found_it = False
for r in resources:
    if r["name"] == kv_name:
        found_it = True
if found_it:
    checkpoints = [{"total": 1, "result": 0}]
else:
    checkpoints = [{"total": 1, "result": 1}]

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
