You have:
1. A source keyvault
2. A target storage account

Your job is to:
1. Create a new blob container 'azuretasks-kv-read-backup' if it doesn's exist in target storage account
2. Back up each secret in source keyvault to a new blob in this container. The name of the blob should be the same as the secret name (this is the same as the last field in the secret id, e.g. if the id is http://foo/bar/bas, then the secret name is 'bas'.
