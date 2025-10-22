import os
import sys
import time
from pathlib import Path

import requests
from azure.identity import EnvironmentCredential
from requests.exceptions import Timeout
from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg_name = "rg-poppy"
api_version = "2024-11-01"

print('Sleep to make sure everything is provisioned and changes are propagated')
time.sleep(600)

def run_eval():
    resources = azure_ops.list_resources_in_rg(sub_id, rg_name)
    api_app_name = None
    for rsrc in resources:
        if rsrc["type"] == "Microsoft.Web/sites" and "api" in rsrc["name"]:
            api_app_name = rsrc["name"]
            print(f"Web app resource name: {api_app_name}")
    if api_app_name is None:
        print("The API web app not found")
        return 0

    cred = EnvironmentCredential()
    token = cred.get_token("https://management.azure.com/.default").token
    url = f"https://management.azure.com/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.Web/sites/{api_app_name}?api-version={api_version}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    resp = resp.json()
    app_url = resp["properties"]["defaultHostName"]
    print("API web app URL:", app_url)

    todo_list_url = f"https://{app_url}/lists"
    print(f"Calling this url: {todo_list_url}")
    try:
        res = requests.get(todo_list_url, timeout=10)
        if res.status_code == 503:
            print("Got 503. Wait for 10 seconds and try again. Maybe it is restarting")
            time.sleep(10)
            res = requests.get(todo_list_url, timeout=10)
    except Timeout:
        try:
            print("Request timed out. Give it another shot")
            res = requests.get(todo_list_url, timeout=15)
        except Timeout:
            print("Request timed out again. Give it a score of zero")
            return 0

    try:
        res.raise_for_status()
    except Exception as e:
        print("Got another exception. Give it a score of zero.")
        print(e.args[0])
        return 0

    print("Status code:", res.status_code)
    print("Response: ")
    pprint(res.json())
    print("Success! Give it a score of one.")
    return 1


score = run_eval()
print()
checkpoints = [{"total": 1, "result": score}]
output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
