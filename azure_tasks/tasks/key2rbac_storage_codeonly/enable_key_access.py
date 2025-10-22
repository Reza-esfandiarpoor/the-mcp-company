import os
import sys
sys.path.append("../../utils")

from azure_ops import (
    enable_storage_account_key_auth
)

sub_id = os.environ["AZTASK_SUBSCRIPTION_ID"]
rg = "azuretasks_key2rbac_storage_codeonly"
storage_account_name = "key2rbacstrgcodesarz4"


# Now disable key based auth
enable_storage_account_key_auth(sub_id, rg, storage_account_name)
