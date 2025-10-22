#!/usr/bin/env bash

terraform init --upgrade
terraform apply -auto-approve -var "taskkvname=mykv${EXP_UUID}"
