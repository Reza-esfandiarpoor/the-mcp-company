#!/usr/bin/env bash

set -e

rot13() {
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

# get the path to the root of the repo
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=$(dirname $(dirname "${SCRIPT_PATH}"))

echo "Setting the environment variables for authentication with Azure"
source "${REPO_ROOT}/azure_tasks/utils/helper_snippets.sh"
set_azure_creds "${REPO_ROOT}/azure_tasks"

echo "Running the server"
python "${REPO_ROOT}/mcp_servers/azure_v2/main_azure_mcp.py"
