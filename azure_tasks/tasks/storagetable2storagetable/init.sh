#!/usr/bin/env bash

if [[ -z "${AZTASK_PYTHON_CMD}" ]]; then
    AZTASK_PYTHON_CMD='python3'
fi

terraform init --upgrade
terraform apply -auto-approve -var "storageaccountname=sacct${EXP_UUID}"
$AZTASK_PYTHON_CMD -m pip install requests azure-identity 
sleep 10
$AZTASK_PYTHON_CMD init_table.py
