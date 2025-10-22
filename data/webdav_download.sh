#!/bin/bash

# Exit on any unexpected error
trap 'rm -- "$0"' EXIT
set -e

REMOTE_FILE_PATH="$1"
LOCAL_DEST_PATH="$2"
WEBDAV_URL="http://localhost:8092/remote.php/webdav"

# Normalize remote file URL
REMOTE_URL="$WEBDAV_URL/$REMOTE_FILE_PATH"


RESPONSE=$(curl -u theagentcompany:theagentcompany -s -X PROPFIND "$REMOTE_URL" -H "Depth: 0")

if ! echo "$RESPONSE" | grep -q "<d:response>"; then
    echo "Error: $REMOTE_FILE_PATH Does not exist on the remote server."
    exit 1
fi

if echo "$RESPONSE" | grep -iqE "<[^>]*resourcetype[^>]*>[^<]*<[^>]*collection[^>]*/?>"; then
    echo "Error: $REMOTE_FILE_PATH is a directory. You should provide a file."
    exit 1
fi

# Ensure local destination directory exists
DEST_DIR=$(dirname "$LOCAL_DEST_PATH")
if [ ! -d "$DEST_DIR" ]; then
    mkdir -p "$DEST_DIR"
fi

# Download the file
curl -u theagentcompany:theagentcompany -o "$LOCAL_DEST_PATH" "$REMOTE_URL"
