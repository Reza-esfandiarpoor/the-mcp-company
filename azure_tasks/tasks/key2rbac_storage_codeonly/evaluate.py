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

print('Sleep for 10 minutes to make sure changes are in effect')
time.sleep(600)

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg = "azuretasks_key2rbac_storage_codeonly"
sa = "key2rbacstrgcodesarz4"


function_url = "https://pyfunc-blob-demo-coderz4.azurewebsites.net/api/MyFunction"
headers = {
    "Content-Type": "application/json"
}
payload = {
    "filename": "example.txt",
    "container": "mycontainer"
}

try:
    print('Calling function app url')
    response = requests.get(function_url, json=payload, headers=headers, timeout=20)
    response.raise_for_status()
    score = 1
except:
    print('Fail: function call failed')
    score = 0

checkpoints = [{"total": 1, "result": score}]

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
