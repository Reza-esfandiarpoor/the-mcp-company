import os
import sys
from pathlib import Path

import requests

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
exp_uuid = os.environ["EXP_UUID"]

storage_acct = f"sacct{exp_uuid}"
resource_group = "azuretasks_static_website"

checkpoints = []


def ckpt(s):
    checkpoints.append({"total": 1, "result": s})


url = azure_ops.get_static_website_url_arm(sub_id, resource_group, storage_acct)
resp = requests.get(url)
print("index content\n", resp.content.decode("utf-8"), "\n")
if "Capybaras are great" not in resp.content.decode("utf-8"):
    ckpt(0)
else:
    ckpt(1)

notfound_url = f"{url}/nothere.html"
resp = requests.get(notfound_url)
print("not found content\n", resp.content.decode("utf-8"), "\n")
if "no Capybaras found here" not in resp.content.decode("utf-8"):
    ckpt(0)
else:
    ckpt(1)


output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
