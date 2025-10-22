#!/usr/bin/env bash

####################################
# prep env
####################################
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"
source "${SCRIPT_DIR}/../../utils/helper_snippets.sh"
set_azure_creds "${SCRIPT_DIR}/../.."


## Task specific setup

if [[ -z "${EXP_UUID}" ]]; then
    echo "For this task you have to set a globally unique value for 'EXP_UUID'"
    exit 1
fi
