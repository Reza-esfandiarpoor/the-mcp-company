#!/usr/bin/env bash

terraform init --upgrade
terraform apply -auto-approve -var "storageaccountname=sacct${EXP_UUID}"
