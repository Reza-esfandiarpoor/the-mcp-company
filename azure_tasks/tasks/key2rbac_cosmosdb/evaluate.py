import os
import requests
import sys
from pathlib import Path
import time

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####

print('Sleeping to make sure all changes are in effect')
time.sleep(600)

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg = "azuretasks_key2rbac_cosmosdb"
cosmosdb_account_name = "cosmos-key2rbac-demo"

def run_eval():
    props = azure_ops.get_cosmosdb_account_properties(sub_id, rg, cosmosdb_account_name)
    if not props['properties']['disableLocalAuth']:
        print('Fail: did not disable shared key access')
        return 0


    function_url = "https://pyfunc-cosmosdb-demorz1.azurewebsites.net/api/TestDbAccess"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "filename": "example.txt",
        "container": "mycontainer"
    }

    try:
        response = requests.get(function_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
    except:
        print('Fail: function call failed')
        return 0
    return 1

score = run_eval()
checkpoints = [{"total": 1, "result": score}]

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
