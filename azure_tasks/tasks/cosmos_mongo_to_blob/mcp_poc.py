import os
import sys
from pathlib import Path

from rich.pretty import pprint

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
from azure_mcp_ops import call_mcp_tool_parse

mcp_url = os.environ.get("AZTASK_MCP_SERVER_URL", "http://localhost:51468/sse")

####


exp_uuid = os.environ["EXP_UUID"]
sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
storage_acct_name = "companystore" + exp_uuid
blob_container_name = "docs"
container_name = "mongobackup"
rg_name = "rg-ducky"

####################
####################
####################

print("> Find Cosmosdb account name")
resp = call_mcp_tool_parse(
    mcp_url,
    "cosmos-db_DatabaseAccounts_ListByResourceGroup",
    {"subscriptionId": sub_id, "resourceGroupName": rg_name},
)
db_acct = None
for item in resp["value"]:
    if item["type"] == "Microsoft.DocumentDB/databaseAccounts":
        db_acct = item["name"]
        db_loc = item["location"]
    print(item["type"])
assert db_acct is not None

print(f"> Create storage account")
resp = call_mcp_tool_parse(
    mcp_url,
    "storage_StorageAccounts_Create",
    {
        "resourceGroupName": rg_name,
        "accountName": storage_acct_name,
        "subscriptionId": sub_id,
        "sku": {"name": "Standard_LRS"},
        "kind": "StorageV2",
        "location": "eastus",
    },
)

print(f"> Create blob container")
resp = call_mcp_tool_parse(
    mcp_url,
    "blob_BlobContainers_Create",
    {
        "containerName": blob_container_name,
        "accountName": storage_acct_name,
        "resourceGroupName": rg_name,
        "subscriptionId": sub_id,
        "properties": {},
    },
)

print(f"> Get storage account keys")
resp = call_mcp_tool_parse(
    mcp_url,
    "storage_StorageAccounts_ListKeys",
    {
        "accountName": storage_acct_name,
        "resourceGroupName": rg_name,
        "subscriptionId": sub_id,
    },
)
storage_acct_key = resp["keys"][0]["value"]

print(f"> Get db connection string")
resp = call_mcp_tool_parse(
    mcp_url,
    "cosmos-db_DatabaseAccounts_ListConnectionStrings",
    {
        "accountName": db_acct,
        "resourceGroupName": rg_name,
        "subscriptionId": sub_id,
    },
)
db_conn_str = resp["connectionStrings"][0]["connectionString"]


print(f"> Create container")
resp = call_mcp_tool_parse(
    mcp_url,
    "containerInstance_ContainerGroups_CreateOrUpdate",
    {
        "resourceGroupName": rg_name,
        "subscriptionId": sub_id,
        "containerGroupName": container_name,
        "location": "eastus",
        "properties": {
            "containers": [
                {
                    "name": "mongo-change-backup",
                    "properties": {
                        "image": "mcr.microsoft.com/devcontainers/python:3.11-bullseye",
                        "command": [
                            "/bin/sh",
                            "-c",
                            "set -e\nmkdir -p /app\npip install --no-cache-dir pymongo azure-storage-blob\ncat >/app/run.py <<'PY'\n#!/usr/bin/env python3\nimport os, time, datetime, threading, sys\nfrom pymongo import MongoClient\nfrom azure.storage.blob import BlobServiceClient\nfrom bson import json_util\n\nMONGODB_URI = os.environ['MONGODB_URI']\nBLOB_ACCOUNT_NAME = os.environ['BLOB_ACCOUNT_NAME']\nBLOB_ACCOUNT_KEY = os.environ['BLOB_ACCOUNT_KEY']\nBLOB_CONTAINER = os.environ.get('BLOB_CONTAINER','rawdocs')\n\nbsc = BlobServiceClient(account_url=f\"https://{BLOB_ACCOUNT_NAME}.blob.core.windows.net\", credential=BLOB_ACCOUNT_KEY)\ncontainer_client = bsc.get_container_client(BLOB_CONTAINER)\ntry:\n    container_client.create_container()\nexcept Exception:\n    pass\n\nclient = MongoClient(MONGODB_URI, tz_aware=False)\nignored_dbs = set(['admin','local','config'])\nactive_watchers = {}\n\ndef upload(doc):\n    ts = datetime.datetime.utcnow().strftime(\"%Y%m%dT%H%M%S%fZ\") + \".json\"\n    data = json_util.dumps(doc, ensure_ascii=False)\n    container_client.upload_blob(name=ts, data=data, overwrite=False)\n\ndef watch_collection(dbname, collname):\n    coll = client[dbname][collname]\n    pipeline = [ {'$match': {'operationType': {'$in': ['insert', 'update', 'replace']}}}, {'$project': {'_id': 1,  'fullDocument': 1, 'ns': 1, 'documentKey': 1, }}] \n    while True:\n        try:\n            with coll.watch(pipeline, full_document='updateLookup') as stream:\n                for change in stream:\n                    doc = change.get('fullDocument', {})\n                    try:\n                        upload(doc)\n                    except Exception as e:\n                        print(\"Upload error:\", e, file=sys.stderr)\n        except Exception as e:\n            print(f\"Watcher error on {dbname}.{collname}: {e}\", file=sys.stderr)\n            time.sleep(5)\n\ndef ensure_watchers():\n    while True:\n        try:\n            dbs = [d for d in client.list_database_names() if d not in ignored_dbs]\n            for dbname in dbs:\n                try:\n                    cols = client[dbname].list_collection_names()\n                except Exception as e:\n                    print(f\"List collections error on {dbname}: {e}\", file=sys.stderr)\n                    continue\n                for collname in cols:\n                    key = f\"{dbname}.{collname}\"\n                    if key not in active_watchers:\n                        t = threading.Thread(target=watch_collection, args=(dbname, collname), daemon=True)\n                        active_watchers[key] = t\n                        t.start()\n        except Exception as e:\n            print(\"ensure_watchers loop error:\", e, file=sys.stderr)\n        time.sleep(30)\n\ndef try_cluster_watch():\n    try:\n        with client.watch([{'$match': {'operationType': 'insert'}}]) as stream:\n            for change in stream:\n                doc = change.get('fullDocument', {})\n                upload(doc)\n    except Exception as e:\n        print(\"Cluster-level watch not supported or failed, falling back to per-collection watchers.\", file=sys.stderr)\n        return False\n    return True\n\nif not try_cluster_watch():\n    th = threading.Thread(target=ensure_watchers, daemon=True)\n    th.start()\n    while True:\n        time.sleep(3600)\nPY\npython /app/run.py",
                        ],
                        "environmentVariables": [
                            {"name": "MONGODB_URI", "value": db_conn_str},
                            {"name": "BLOB_ACCOUNT_NAME", "value": storage_acct_name},
                            {"name": "BLOB_ACCOUNT_KEY", "value": storage_acct_key},
                            {"name": "BLOB_CONTAINER", "value": blob_container_name},
                        ],
                        "resources": {"requests": {"memoryInGB": 1, "cpu": 0.5}},
                    },
                }
            ],
            "restartPolicy": "Always",
            "osType": "Linux",
        },
    },
)
