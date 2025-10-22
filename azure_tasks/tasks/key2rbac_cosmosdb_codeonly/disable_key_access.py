import os
import sys

sys.path.append("../../utils")

from azure_ops import disable_cosmosdb_key_auth

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg = "azuretasks_key2rbac_cosmosdb_code"
cosmosdb_account_name = "cosmos-code-key2rbac-demo"

# Now disable key based auth
disable_cosmosdb_key_auth(sub_id, rg, cosmosdb_account_name)
