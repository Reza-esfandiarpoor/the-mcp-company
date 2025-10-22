import os
import time
import requests
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####

print('Sleep for 10 minutes to make sure all changes are in effect')
time.sleep(600)

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg = "azuretasks_key2rbac"
sa = "key2rbacsarz2"

def run_eval():
    props = azure_ops.get_storage_account_properties(sub_id, rg, sa)
    if props['properties']['allowSharedKeyAccess']:
        print('Fail: did not disable shared key access')
        return 0

    function_url = "https://pyfunc-blob-demorz2.azurewebsites.net/api/MyFunction"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "filename": "example.txt",
        "container": "mycontainer"
    }

    try:
        print('call app url')
        response = requests.get(function_url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
    except:
        print('Fail: function call failed')
        return 0
    return 1

score = run_eval()
checkpoints = [{"total": 1, "result": score}]

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
