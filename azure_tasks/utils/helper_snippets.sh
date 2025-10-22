#!/usr/bin/env bash

rot13() {
    # You can run this command on a file. Or pipe data into it.

    if [ $# -eq 0 ]; then
        # No arguments → read from stdin (pipe mode)
        tr 'A-Za-z' 'N-ZA-Mn-za-m'
    else
        # One or more files → apply tr to them
        for file in "$@"; do
            tr 'A-Za-z' 'N-ZA-Mn-za-m' < "$file"
        done
    fi
}

set_azure_creds() {
    # sets azure credentials. Run like
    # set_azure_creds "path/to/azure_tasks". This is the directory that holds the utils and tasks folders
    AZURE_TASKS_PARDIR="${1}"
    if [[ -f "${AZURE_TASKS_PARDIR}/azure_creds.sh" ]]; then
        source "${AZURE_TASKS_PARDIR}/azure_creds.sh"
    elif [[ -f "${AZURE_TASKS_PARDIR}/set_creds.rot13" ]]; then
        source <(rot13 "${AZURE_TASKS_PARDIR}/set_creds.rot13")
    else
        echo "Did not find a file to set the credentials for Azure."
        exit 1
    fi

    export AZURE_TENANT_ID
    export AZURE_CLIENT_ID
    export AZURE_CLIENT_SECRET
    export AZTASK_SUBSCRIPTION_ID

    # setup for terraform
    export TF_VAR_azure_client_id="${AZURE_CLIENT_ID}"
    export ARM_TENANT_ID="${AZURE_TENANT_ID}"
    export ARM_CLIENT_ID="${AZURE_CLIENT_ID}"
    export ARM_CLIENT_SECRET="${AZURE_CLIENT_SECRET}"
    export ARM_SUBSCRIPTION_ID="${AZTASK_SUBSCRIPTION_ID}"

    if [[ -f "${AZURE_TASKS_PARDIR}/isolated_azure_tools.sh" ]]; then
        source "${AZURE_TASKS_PARDIR}/isolated_azure_tools.sh"
    fi
}
