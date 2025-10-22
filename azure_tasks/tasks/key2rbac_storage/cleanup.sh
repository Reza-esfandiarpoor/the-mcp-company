#!/usr/bin/env bash

rg_exists=$(az group exists --name azuretasks_key2rbac)
if [[ "${rg_exists}" == "true" ]]; then
    az group delete --name azuretasks_key2rbac --yes || true
fi

rg_exists=$(az group exists --name azuretasks_key2rbac)
if [[ "${rg_exists}" == "true" ]]; then
    az group wait --name azuretasks_key2rbac --deleted || true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

rm -r .terraform.lock.hcl terraform.tfstate terraform.tfstate.backup .terraform || true
