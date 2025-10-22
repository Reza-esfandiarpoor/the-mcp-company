#!/usr/bin/env bash

terraform init --upgrade
terraform apply -auto-approve -var "translatename=trname${EXP_UUID}" -var "translatedomain=trdomain${EXP_UUID}" -var "taskstoragename=sacct${EXP_UUID}"
