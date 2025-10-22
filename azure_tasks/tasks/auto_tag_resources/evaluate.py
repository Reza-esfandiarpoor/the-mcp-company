import os
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]


restype2tag = {"Microsoft.KeyVault/vaults": "Security"}

try:
    res = azure_ops.list_resources_in_rg(sub_id, "azuretasks_auto_tag_resources")
    all_scores = []
    for r in res:
        name = r["name"]
        print(f"Checking resource {name}\n")
        if r["type"] in restype2tag:
            want_tag = restype2tag[r["type"]]
            if "Category" in r["tags"] and r["tags"]["Category"] == want_tag:
                print("Good\n")
                all_scores.append(1)
            else:
                print("Bad\n")
                all_scores.append(0)
        else:
            print(f"Skipping, resource type ('{r['type']}') not defined")
        pprint(r)
    score = int(all(all_scores))
except:
    score = 0

checkpoints = [{"total": 1, "result": score}]

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
