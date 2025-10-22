#!/bin/bash

# Exit on any error
trap 'rm -- "$0"' EXIT
set -e

LOCAL_FILE="$1"
REMOTE_PATH="$2"
WEBDAV_URL="http://localhost:8092/remote.php/webdav"

# Check if local file exists
if [ ! -f "$LOCAL_FILE" ]; then
    echo "Error: Local file '$LOCAL_FILE' does not exist."
    exit 1
fi

# Extract remote directory path
REMOTE_DIR=$(dirname "$REMOTE_PATH")

# If remote directory is not root, ensure it exists on the server
if [ "$REMOTE_DIR" != "." ] && [ "$REMOTE_DIR" != "/" ]; then
    # Normalize remote directory (remove leading slash)
    NORMALIZED_REMOTE_DIR="${REMOTE_DIR#/}"

    # Split the directory into components and create each level
    IFS='/' read -ra DIR_PARTS <<< "$NORMALIZED_REMOTE_DIR"
    CURRENT_PATH=""
    for PART in "${DIR_PARTS[@]}"; do
        CURRENT_PATH="$CURRENT_PATH/$PART"
        curl -u theagentcompany:theagentcompany -s -o /dev/null -X MKCOL "$WEBDAV_URL/$CURRENT_PATH" || true
    done
fi

# Upload the file
curl -u theagentcompany:theagentcompany -s -T "$LOCAL_FILE" "$WEBDAV_URL/$REMOTE_PATH"
echo "upload successful"
