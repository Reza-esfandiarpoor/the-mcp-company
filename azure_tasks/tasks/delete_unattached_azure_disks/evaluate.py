import os
import sys
import time
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####

time.sleep(30)
sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg_name = "azuretasks_delete_unattached_disks"

res = azure_ops.list_resources_in_rg(subscription_id=sub_id, resource_group=rg_name)

found_disk = False
for r in res:
    if r["name"] == "example-disk2":
        found_disk = True
        break

if found_disk:
    score = 0
else:
    score = 1

checkpoints = [{"total": 1, "result": score}]

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
