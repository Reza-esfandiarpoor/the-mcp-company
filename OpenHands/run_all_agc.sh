#!/usr/bin/env bash

set -e

# export USE_DOCKER_FOR_EVAL='false'
# export DOCKER_EVAL_NO_TIMEOUT='false'

export REPO_ROOT_DIR=$(python3 -c 'from pathlib import Path; print(Path.cwd().parent.absolute().resolve().as_posix())')
export TAGC_EVAL_PARDIR="${REPO_ROOT_DIR}/data/tac_eval_scripts"
export CONFIG_FILE='config.toml'

AGENT_TYPE="${1}"

if [[ "${AGENT_TYPE}" == "cua" ]]; then
    echo '###########################'
    echo "Required config changes:"
    echo '- set correct system prompt file'
    echo '###########################'

    echo 'Using CUA agent'

elif [[ "${AGENT_TYPE}" == "dense_retrieval" ]]; then
    echo '###########################'
    echo "Required config changes:"
    echo '- Config mcp servers'
    echo '- set correct system prompt file'
    echo '- disable browsing'
    echo '###########################'

    echo 'Using function calling agent with dense retrieval'
    export TAGC_TASK_PARDIR="${REPO_ROOT_DIR}/data/the_agent_company_tasks_fn_with_group"
    export IS_USING_TOOLS='true'

elif [[ "${AGENT_TYPE}" == "gt_tools" ]]; then
    echo '###########################'
    echo "Required config changes:"
    echo '- Config mcp servers'
    echo '- set correct system prompt file'
    echo '- disable browsing'
    echo '###########################'

    echo 'Using function calling agent with ground truth tools per task'
    export TAGC_TASK_PARDIR="${REPO_ROOT_DIR}/data/the_agent_company_tasks_fn_with_group"
    export GT_TOOL_PATH='data/task_fn_matching_v1_manual.json'
    export IS_USING_TOOLS='true'

else
    echo 'You should choose an agent type'
    exit 1
fi

if [[ "${RUN_AZURE_TASKS}" == "true" ]]; then
    bash all_azure_cmds.sh
else
    bash all_agc_cmds.sh
fi

docker volume prune -f
docker container prune -f
