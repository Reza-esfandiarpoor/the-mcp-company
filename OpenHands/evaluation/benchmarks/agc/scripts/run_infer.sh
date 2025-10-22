#!/usr/bin/env bash

##################################################################################################
# Adapted from https://github.com/TheAgentCompany/TheAgentCompany/blob/main/evaluation/run_eval.sh
##################################################################################################

set -e

# Exit on any error would be useful for debugging
if [ -n "$DEBUG" ]; then
    set -e
fi


create_artifact_dir_with_correct_owner() {
    TARGET_RES_PARDIR='exp_artifacts'
    mkdir -p "${TARGET_RES_PARDIR}"
    USERNAME_CANDIDATES=(reza azureuser ubuntu t-rezae)
    owner="$(stat -c %U "${TARGET_RES_PARDIR}")"
    if [[ "${EUID:-$(id -u)}" -eq 0 ]] && [[ "$owner" == "root" ]]; then
        # we are running as root and the directory is also owned by root
        # Find which of the candidate users exists (expect exactly one)
        found_user=""
        for u in "${USERNAME_CANDIDATES[@]}"; do
            if id -u "$u" > /dev/null 2>&1; then
                if [[ -n "$found_user" ]]; then
                    echo "Error: multiple candidate users found: '$found_user' and '$u'." >&2
                    exit 1
                fi
                found_user="$u"
            fi
        done
        if [[ -z "$found_user" ]]; then
            echo "Error: none of the expected users exist on this system." >&2
            exit 1
        fi
        chown "$found_user":"$(id -gn "$found_user")" "$TARGET_RES_PARDIR"
    fi
}

gen_uuid() {
    python3 -c 'from uuid import uuid4; print(uuid4().hex)'
}

# AGENT_LLM_CONFIG is the config name for the agent LLM
# In config.toml, you should have a section with the name
# [llm.<AGENT_LLM_CONFIG>], e.g. [llm.agent]
AGENT_LLM_CONFIG="agent"

# ENV_LLM_CONFIG is the config name for the environment LLM,
# used by the NPCs and LLM-based evaluators.
# In config.toml, you should have a section with the name
# [llm.<ENV_LLM_CONFIG>], e.g. [llm.env]
ENV_LLM_CONFIG="env"

# OUTPUTS_PATH is the path to save trajectories and evaluation results
OUTPUTS_PATH="exp_artifacts/outputs"
create_artifact_dir_with_correct_owner

# SERVER_HOSTNAME is the hostname of the server that hosts all the web services,
# including RocketChat, ownCloud, GitLab, and Plane.
SERVER_HOSTNAME="localhost"

# VERSION is the version of the task images to use
# If a task doesn't have a published image with this version, it will be skipped
# 12/15/2024: this is for forward compatibility, in the case where we add new tasks
# after the 1.0.0 release
VERSION="1.0.0"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --agent-llm-config)
            AGENT_LLM_CONFIG="$2"
            shift 2
            ;;
        --env-llm-config)
            ENV_LLM_CONFIG="$2"
            shift 2
            ;;
        --agent-config)
            AGENT_CONFIG="$2"
            shift 2
            ;;
        --outputs-path)
            OUTPUTS_PATH="$2"
            shift 2
            ;;
        --server-hostname)
            SERVER_HOSTNAME="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --start-percentile)
            START_PERCENTILE="$2"
            shift 2
            ;;
        --end-percentile)
            END_PERCENTILE="$2"
            shift 2
            ;;
        --config-file)
            OH_CONFIG_FILE="$2"
            shift 2
            ;;
        --start)
            START_LINE="$2"
            shift 2
            ;;
        --end)
            END_LINE="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

if [[ -z "${AGENT_CONFIG}" ]]; then
    AGENT_CONFIG='agent'
fi

if [[ -z "${OH_CONFIG_FILE}" ]]; then
    OH_CONFIG_FILE='config.toml'
fi

if [[ -z "${START_LINE}" ]]; then
    START_LINE='1'
fi

if [[ -z "${END_LINE}" ]]; then
    END_LINE='175'
fi

if [ "$START_LINE" -lt 1 ] || [ "$END_LINE" -gt 175 ]; then
    echo "Error: start and end lines must be between 1 and 175 inclusive. Got: [${START_LINE}, ${END_LINE}]"
    exit 1
fi

# Convert outputs_path to absolute path
if [[ ! "$OUTPUTS_PATH" = /* ]]; then
    # If path is not already absolute (doesn't start with /), make it absolute
    OUTPUTS_PATH="$(cd "$(dirname "$OUTPUTS_PATH")" 2> /dev/null && pwd)/$(basename "$OUTPUTS_PATH")"
fi

echo "Using agent LLM config: $AGENT_LLM_CONFIG"
echo "Using environment LLM config: $ENV_LLM_CONFIG"
echo "Outputs path: $OUTPUTS_PATH"
echo "Server hostname: $SERVER_HOSTNAME"
echo "Version: $VERSION"
echo "Start Line: $START_LINE"
echo "End Line: $END_LINE"


if [ -f './.env' ]; then
  source '.env'
fi

TASKS_FILE_LIST='../data/tac_task_list.md'

total_lines=$(cat "${TASKS_FILE_LIST}" | grep "ghcr.io/theagentcompany" | wc -l)
if [ "$total_lines" -ne 175 ]; then
    echo "Error: Expected 175 tasks in tasks.md but found $total_lines lines"
    exit 1
fi

# Create a temporary file with just the desired range
_UUID=$(gen_uuid)
temp_file="/tmp/tasks_${START_LINE}_${END_LINE}_${_UUID}.md"
sed -n "${START_LINE},${END_LINE}p" "${TASKS_FILE_LIST}" > "$temp_file"

while IFS= read -r task_image; do
    # Remove prefix using ## to remove longest matching pattern from start
    task_name=${task_image##ghcr.io/theagentcompany/}

    # Remove suffix using % to remove shortest matching pattern from end
    task_name=${task_name%-image:*}
    echo "Use task image $task_image, task name $task_name..."

    export RE_TRACE_NAME="${task_name}"

    # Check if evaluation file exists
    if [ -f "$OUTPUTS_PATH/eval_${task_name}-image.json" ]; then
        echo "Skipping $task_name - evaluation file already exists"
        continue
    fi


    ########### run server with gt tools only
    if [[ ! -z "${GT_TOOL_PATH}" ]]; then
        GT_TOOL_NAMES=$(python3 ../data/select_tools_for_task.py "${GT_TOOL_PATH}" "${task_name}")
        curl -X POST http://localhost:7879/admin/set_tools \
            -H 'Content-Type: application/json' \
            -d "${GT_TOOL_NAMES}"
        until nc -z -w 2 "localhost" "7879"; do
            echo "Waiting for MCP server with preselected tools"
            sleep 2
        done
    fi
    ###########################################

    docker pull $task_image

    if [[ -z "${RE_PY_INTERP}" ]]; then
        RE_PY_INTERP="poetry run python"
    fi

    # Build the Python command
    COMMAND="${RE_PY_INTERP} -m evaluation.benchmarks.agc.run_infer \
            --agent-llm-config \"$AGENT_LLM_CONFIG\" \
            --env-llm-config \"$ENV_LLM_CONFIG\" \
            --outputs-path \"$OUTPUTS_PATH\" \
            --server-hostname \"$SERVER_HOSTNAME\" \
            --config-file \"${OH_CONFIG_FILE}\" \
            --task-image-name \"$task_image\""

    # Add agent-config if it's defined
    if [ -n "$AGENT_CONFIG" ]; then
        COMMAND="$COMMAND --agent-config $AGENT_CONFIG"
    fi

    export PYTHONPATH=evaluation/benchmarks/agc:$PYTHONPATH \
                                                            && eval "$COMMAND"

    unset RE_TRACE_NAME

    # Prune unused images and volumes
    # docker image rm "$task_image"
    # docker images "ghcr.io/all-hands-ai/runtime" -q | xargs -r docker rmi -f
    docker volume prune -f
    docker container prune -f
done < "$temp_file"

rm "$temp_file"

echo "All evaluation completed successfully!"
