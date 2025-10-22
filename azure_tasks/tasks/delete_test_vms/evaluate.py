import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg_name = "azuretasks_delete_test_vms"

res = azure_ops.list_resources_in_rg(sub_id, rg_name)

vms_found = []
for r in res:
    name = r["name"]
    print(f"Checking resource {name}")
    if r["type"] == "Microsoft.Compute/virtualMachines":
        vms_found.append(r["name"])


checkpoints = list()


def ckpt(sc):
    checkpoints.append({"total": 1, "result": sc})


if "maybedelete-vm1" in vms_found:
    ckpt(0)
else:
    ckpt(1)

if "maybedelete-test-vm-2" in vms_found:
    ckpt(0)
else:
    ckpt(1)

if "maybedelete-vm-3" in vms_found:
    ckpt(1)
else:
    ckpt(0)

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
