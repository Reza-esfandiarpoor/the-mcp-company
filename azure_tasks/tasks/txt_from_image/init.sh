#!/usr/bin/env bash

curl -OLJ https://huggingface.co/datasets/BatsResearch/themcpcompany_artifacts/resolve/main/image.png

terraform init --upgrade
terraform apply -auto-approve -var "visionname=vis${EXP_UUID}" -var "visiondomain=domain${EXP_UUID}" -var "taskstoragename=sacct${EXP_UUID}"
