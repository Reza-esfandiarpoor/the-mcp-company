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
rg = "azuretasks_key2rbac_cosmosdb_code"
cosmosdb_account_name = "cosmos-code-key2rbac-demo"


function_url = "https://pyfunc-cosmosdb-code-demorz3.azurewebsites.net/api/TestDbAccess"
headers = {
    "Content-Type": "application/json"
}
payload = {
    "filename": "example.txt",
    "container": "mycontainer"
}

try:
    print('Calling the function app api')
    response = requests.get(function_url, json=payload, headers=headers, timeout=20)
    response.raise_for_status()
    score = 1
except:
    print('Fail: function call failed')
    score = 0


checkpoints = [{"total": 1, "result": score}]

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
