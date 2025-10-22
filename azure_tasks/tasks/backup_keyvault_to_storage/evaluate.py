import os
import sys
from pathlib import Path

sys.path.append(Path(__file__).parents[2].joinpath("utils").as_posix())
import azure_ops
import helpers

output_path = helpers.check_output_filepath(sys.argv)

####
exp_uuid = os.environ["EXP_UUID"]

secrets = azure_ops.list_kv_secrets(f"kvlt{exp_uuid}")

storage_acct = f"sact{exp_uuid}"
container_name = "azuretasks-kv-read-backup"


def secret_name_from_secret(get_from_me: str) -> str:
    return get_from_me.split("/")[-1]


secret_names = []
for secret in secrets:
    secret_names.append(secret_name_from_secret(secret["id"]))
print("secret names", secret_names)

checkpoints = list()
for secret_name in secret_names:
    blob_exists = azure_ops.blob_exists(storage_acct, container_name, secret_name)
    if not blob_exists:
        print(f"blob for {secret_name} does not exist")
        curr_res = 0
    else:
        secret_value = azure_ops.read_text_from_blob(
            storage_acct, container_name, secret_name
        )
        if len(secret_value) == 0:
            print(f"Missing blob for {secret_name}")
            print("Bad")
            curr_res = 0
        else:
            curr_res = 1
    checkpoints.append({"total": 1, "result": curr_res})

output_result = helpers.aggregate_and_format_results(checkpoints=checkpoints)
helpers.write_json(output_result, output_path)
