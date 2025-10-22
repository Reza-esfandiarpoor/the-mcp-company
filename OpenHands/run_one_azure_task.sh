#!/usr/bin/env bash

####################################################################
# Run the agent for one azure task. It does the following:
#   - Run the init script
#   - Run the agent
#   - Run the eval script
#   - Run the cleanup script
#
# To use it, you should first cd to REPO_ROOT/OpenHands
# Then run the following. TASK_IDX starts from 1
#
#   $ bash run_one_azure_task.sh TASK_IDX
#
# For example
#   $ bash run_one_azure_task.sh 1
####################################################################

set -e

cleanup() {
    ec=$?            # <-- exit code at the moment the trap fired
    if [[ ! "$ec" == "0" ]]; then
        echo "sess: ${CURR_RUN_SESSION_ID} ** Task: ${TASK_NAME}" >> failed_azure_tasks.txt
    fi
    # --- your cleanup here ---
    echo_log "Run cleanup"
    bash -c "source ${TASK_ROOT}/set_env.sh && bash cleanup.sh"
    # --------------------------
    exit "$ec"       # exit with the original status (success or error)
}

echo_log() {
    mytimestamp=$(date +"%m-%d %H:%M")
    echo -e "\e[33m[$mytimestamp] ${@}\e[0m"
}

if [ -f './.env' ]; then
    source '.env'
fi

if [[ -z "${RE_PY_INTERP}" ]]; then
    RE_PY_INTERP="poetry run python"
fi

if [[ -z "${RE_MCP_INTERP}" ]]; then
    RE_MCP_INTERP='python3'
fi

$RE_MCP_INTERP -c 'import azure.identity'

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=$(dirname "${SCRIPT_PATH}")

##### Set the environment  variables

# Optional config variables
# export AGC_SETUP_AND_WAIT='false'
# export AGC_BUILD_IMAGE_ONLY='false'
# export USE_DOCKER_FOR_EVAL='false'
# export DOCKER_EVAL_NO_TIMEOUT='false'

export MLFLOW_PROXY_URL='http://localhost:7891'
export IS_USING_TOOLS='true'

# export CONFIG_FILE='config.toml'
if [[ -z "${CONFIG_FILE}" ]]; then
    echo "You must set the 'CONFIG_FILE' variable"
    exit 1
fi

##################################

echo '###########################'
echo "Required config changes:"
echo '- Config mcp servers'
echo '- set correct system prompt file'
echo '- disable browsing'
echo '###########################'

##################################
##################################
##################################

# Name of the azure task
TASK_NAME=$(sed -n "${1},${1}p" "${REPO_ROOT}/azure_tasks/azure_task_list.txt")
TASK_ROOT="${REPO_ROOT}/azure_tasks/tasks/${TASK_NAME}"
OUTPUT_PARDIR="azure_outputs"
mkdir -p "${OUTPUT_PARDIR}"
mkdir -p "${OUTPUT_PARDIR}/streams_for_eval"
mkdir -p "${OUTPUT_PARDIR}/trajectories"
OUTPUT_PARDIR=$(bash -c "cd ${OUTPUT_PARDIR} && pwd")

if [[ -f "${OUTPUT_PARDIR}/eval_${TASK_NAME}.json" ]]; then
    echo_log "Skipping $TASK_NAME - evaluation file already exists"
    exit 0
fi

export RE_TRACE_NAME="${TASK_NAME}"

if [[ -z "${EXP_UUID}" ]]; then
    export EXP_UUID='rz1'
fi

CURR_UUID=$(python3 -c 'from uuid import uuid4; print(uuid4().hex)')
TASK_WORKDIR="/tmp/${CURR_UUID}"
mkdir -p "${TASK_WORKDIR}"

echo_log "TASK temp dir: ${TASK_WORKDIR}"
echo_log "Current task: ${TASK_NAME}"

cat "${TASK_ROOT}/task.md" >> "${TASK_WORKDIR}/task.md"
echo -e '\nUse the following information to complete the task if needed:' >> "${TASK_WORKDIR}/task.md"
bash -c "source ${TASK_ROOT}/set_env.sh && bash task_suffix.sh" >> "${TASK_WORKDIR}/task.md"

echo '======================================================================'
echo '============================= Task Description ======================='
echo '======================================================================'
cat "${TASK_WORKDIR}/task.md"
echo
echo '======================================================================'
echo '======================================================================'

########### run server with gt tools only
if [[ ! -z "${GT_TOOL_PATH}" ]] || [[ "${USE_GT_TOOLS}" == "true" ]]; then
    GT_TOOL_NAMES=$(cat "${TASK_ROOT}/gt_tools.json")
    curl --fail-with-body -X POST http://localhost:7880/admin/set_tools \
        -H 'Content-Type: application/json' \
        -d "${GT_TOOL_NAMES}"
    until nc -z -w 2 "localhost" "7880"; do
        echo "Waiting for MCP server with preselected tools"
        sleep 2
    done
fi
###########################################

echo_log 'Init terraform'

if [[ ! "${NO_SET_TRAP}" == "true" ]]; then
    trap 'cleanup' EXIT
fi

if [[ "${TASK_NAME}" == "storagetable2storagetable" ]]; then
    export AZTASK_PYTHON_CMD="${RE_MCP_INTERP}"
fi

bash -c "source ${TASK_ROOT}/set_env.sh && bash init.sh"

export RE_AGENT_TRAJ_PATH="${OUTPUT_PARDIR}/trajectories/${TASK_NAME}.json"

echo_log "Start agent"
$RE_PY_INTERP -m openhands.core.main \
    --config-file "${CONFIG_FILE}" \
    -c CodeActAgent \
    -l agent \
    -i 100 \
    -f "${TASK_WORKDIR}/task.md"

echo_log "Run evaluation"

bash -c "source ${TASK_ROOT}/set_env.sh && ${RE_MCP_INTERP} -u evaluate.py ${OUTPUT_PARDIR}/eval_${TASK_NAME}.json 2>&1 | tee ${OUTPUT_PARDIR}/streams_for_eval/${TASK_NAME}.txt"

echo_log "Done with ${TASK_NAME}"
