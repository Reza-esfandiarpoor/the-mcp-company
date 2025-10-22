#!/usr/bin/env bash

if [[ -z "${CONFIG_FILE}" ]]; then
    echo 'You have to set the "CONFIG_FILE" env var.'
    exit 1
fi
export CONFIG_FILE

export CURR_RUN_SESSION_ID=$(date)

EXP_UUID_BASE="rzx"

EXP_UUID="${EXP_UUID_BASE}1" bash run_one_azure_task.sh 1
EXP_UUID="${EXP_UUID_BASE}2" bash run_one_azure_task.sh 2
EXP_UUID="${EXP_UUID_BASE}3" bash run_one_azure_task.sh 3
EXP_UUID="${EXP_UUID_BASE}4" bash run_one_azure_task.sh 4
EXP_UUID="${EXP_UUID_BASE}5" bash run_one_azure_task.sh 5
EXP_UUID="${EXP_UUID_BASE}6" bash run_one_azure_task.sh 6
EXP_UUID="${EXP_UUID_BASE}7" bash run_one_azure_task.sh 7
EXP_UUID="${EXP_UUID_BASE}8" bash run_one_azure_task.sh 8
EXP_UUID="${EXP_UUID_BASE}9" bash run_one_azure_task.sh 9
EXP_UUID="${EXP_UUID_BASE}10" bash run_one_azure_task.sh 10
EXP_UUID="${EXP_UUID_BASE}11" bash run_one_azure_task.sh 11
EXP_UUID="${EXP_UUID_BASE}12" bash run_one_azure_task.sh 12
EXP_UUID="${EXP_UUID_BASE}13" bash run_one_azure_task.sh 13
EXP_UUID="${EXP_UUID_BASE}14" bash run_one_azure_task.sh 14
EXP_UUID="${EXP_UUID_BASE}15" bash run_one_azure_task.sh 15
EXP_UUID="${EXP_UUID_BASE}16" bash run_one_azure_task.sh 16
EXP_UUID="${EXP_UUID_BASE}17" bash run_one_azure_task.sh 17
