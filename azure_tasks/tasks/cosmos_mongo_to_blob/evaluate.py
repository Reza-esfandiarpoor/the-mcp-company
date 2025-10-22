import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from subprocess import run
from uuid import uuid4

import requests
from azure.identity import EnvironmentCredential
from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####

checkpoints = []


def ckpt(s):
    checkpoints.append({"total": 1, "result": s})


def ensure_access_to_stg(rg_name, acct_name):

    script_content = f"""#!/usr/bin/env

RG='{rg_name}'
SA='{acct_name}'
SA_ID=$(az storage account show -g "$RG" -n "$SA" --query id -o tsv)
SP_OBJECT_ID=$(az ad sp show --id "$AZURE_CLIENT_ID" --query id -o tsv)
az role assignment create \
  --assignee-object-id "$SP_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Storage Account Contributor" \
  --scope "$SA_ID"
"""
    scpath = "/tmp/" + uuid4().hex + ".sh"
    with open(scpath, "w") as f:
        f.write(script_content + "\n")
    run(["bash", scpath], timeout=20, check=False)


exp_uuid = os.environ["EXP_UUID"]
sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
storage_acct_name = "companystore" + exp_uuid
blob_container_name = "docs"
container_name = "mongobackup"
rg_name = "rg-ducky"

print("Sleep for 10 minutes to make sure everything is provisioned and changes are propagated")
time.sleep(600)

cred = EnvironmentCredential()
token = cred.get_token("https://management.azure.com/.default")
token = token.token

def run_eval():
    print(f"> find the web app name")
    resources = azure_ops.list_resources_in_rg(sub_id, rg_name)
    api_app_name = None
    for rsrc in resources:
        if rsrc["type"] == "Microsoft.Web/sites" and "api" in rsrc["name"]:
            api_app_name = rsrc["name"]
            print(f"Web app resource name: {api_app_name}")
    assert api_app_name is not None

    print(f"> find the web app address")
    url = f"https://management.azure.com/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.Web/sites/{api_app_name}?api-version=2024-11-01"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    resp = resp.json()
    app_url = resp["properties"]["defaultHostName"]
    print("API web app URL:", app_url)

    print("> Check if storage account is created")
    url = f"https://management.azure.com/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts?api-version=2019-06-01"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    resp = resp.json()
    all_saccts = [item["name"] for item in resp["value"]]
    print('List of existing storage accounts:', ', '.join(all_saccts))

    if storage_acct_name in all_saccts:
        ckpt(1)
    else:
        ckpt(0)
        ckpt(0)
        ckpt(0)
        print(f"RES: storage account '{storage_acct_name}' is not created")
        return

    print("> Check if blob container is created")
    url = f"https://management.azure.com/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/{storage_acct_name}/blobServices/default/containers?api-version=2019-06-01"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    resp = resp.json()
    all_ct_names = [item["name"] for item in resp["value"]]
    print('List of existing containers:', ', '.join(all_ct_names))

    if blob_container_name in all_ct_names:
        ckpt(1)
    else:
        ckpt(0)
        ckpt(0)
        print(f"RES: Container {blob_container_name} is not created")
        return

    ensure_access_to_stg(rg_name, storage_acct_name)

    print("> Get the number of blobs before insert")
    stg_token = cred.get_token("https://storage.azure.com/.default").token
    url = f"https://{storage_acct_name}.blob.core.windows.net/{blob_container_name}?restype=container&comp=list&flat"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {stg_token}", "x-ms-version": "2025-11-05"},
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    orig_blobs = [b.find("Name").text for b in root.findall(".//Blob")]
    print(f"Num orig blobs: {len(orig_blobs)}")

    print("Insert new item into mongodb")
    todo_list_url = f"https://{app_url}/lists"
    body = {"name": uuid4().hex[:8], "description": "mydescription"}
    requests.post(todo_list_url, json=body)

    time.sleep(5)

    print(f"> Get the number of blobs after insert")
    stg_token = cred.get_token("https://storage.azure.com/.default").token
    url = f"https://{storage_acct_name}.blob.core.windows.net/{blob_container_name}?restype=container&comp=list&flat"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {stg_token}", "x-ms-version": "2025-11-05"},
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    new_blobs = [b.find("Name").text for b in root.findall(".//Blob")]
    print(f"Num new blobs: {len(new_blobs)}")

    if len(new_blobs) == len(orig_blobs) + 1:
        ckpt(1)
    else:
        print("RES: New items are not backed up into blob storage")
        print(f"Num blobs orig: {len(orig_blobs)} ** Num blobs new: {len(new_blobs)}")
        ckpt(0)


score = run_eval()
print()
output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
