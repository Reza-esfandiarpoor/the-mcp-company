#!/usr/bin/env bash

terraform init --upgrade
terraform apply -auto-approve -var "taskkvfrom=kvfrom${EXP_UUID}" -var "taskkvto=kvto${EXP_UUID}"
