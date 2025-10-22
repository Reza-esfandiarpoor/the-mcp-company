#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/todo-python-mongo-terraform"

unset ARM_CLIENT_ID ARM_CLIENT_SECRET ARM_TENANT_ID ARM_SUBSCRIPTION_ID ARM_USE_MSI ARM_USE_OIDC ARM_USE_AZUREAD

azd down --no-prompt --force --purge
rm -r .azure || true
