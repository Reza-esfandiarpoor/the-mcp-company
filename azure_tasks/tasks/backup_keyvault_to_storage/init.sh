#!/usr/bin/env bash

terraform init --upgrade
terraform apply -auto-approve -var "keyvaultname=kvlt${EXP_UUID}" -var "storageaccountname=sact${EXP_UUID}"
