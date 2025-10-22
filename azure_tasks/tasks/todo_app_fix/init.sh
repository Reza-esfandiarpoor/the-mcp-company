#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/todo-python-mongo-terraform"

ENV_NAME='poppy'
SUB_ID="${AZTASK_SUBSCRIPTION_ID}"
REGION="eastus2"

unset ARM_CLIENT_ID ARM_CLIENT_SECRET ARM_TENANT_ID ARM_SUBSCRIPTION_ID ARM_USE_MSI ARM_USE_OIDC ARM_USE_AZUREAD

azd env new "$ENV_NAME" --subscription "$SUB_ID" --location "$REGION" --no-prompt || azd env select "$ENV_NAME" --no-prompt

azd env set AZURE_SUBSCRIPTION_ID "$SUB_ID" --environment "$ENV_NAME"
azd env set AZURE_LOCATION "$REGION" --environment "$ENV_NAME"

# Provision + deploy without prompts
azd up -e "$ENV_NAME" --no-prompt
