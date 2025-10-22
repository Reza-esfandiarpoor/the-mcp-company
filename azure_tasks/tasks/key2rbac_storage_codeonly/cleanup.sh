#!/usr/bin/env bash

if [[ -z "${AZTASK_PYTHON_CMD}" ]]; then
    AZTASK_PYTHON_CMD='python3'
fi

$AZTASK_PYTHON_CMD enable_key_access.py
terraform destroy -auto-approve


RG_NAME='azuretasks_key2rbac_storage_codeonly'

rg_exists=$(az group exists --name "${RG_NAME}")
if [[ "${rg_exists}" == "true" ]]; then
    az group delete --name "${RG_NAME}" --yes || true
fi

rg_exists=$(az group exists --name "${RG_NAME}")
if [[ "${rg_exists}" == "true" ]]; then
    az group wait --name "${RG_NAME}" --deleted || true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

rm -r .terraform.lock.hcl terraform.tfstate terraform.tfstate.backup .terraform || true
