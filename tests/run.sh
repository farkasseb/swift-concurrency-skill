#!/bin/sh
# Verifies the skill's code snippets and factual claims against an installed Xcode.
#
# Xcode selection, first match wins:
#   XCODE=/Applications/Xcode.app tests/run.sh
#   DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer tests/run.sh
#   otherwise the Xcode chosen with xcode-select.
set -eu

if [ -n "${XCODE:-}" ]; then
    if [ -d "$XCODE/Contents/Developer" ]; then
        DEVELOPER_DIR="$XCODE/Contents/Developer"
    else
        DEVELOPER_DIR="$XCODE"
    fi
elif [ -z "${DEVELOPER_DIR:-}" ]; then
    DEVELOPER_DIR="$(xcode-select -p)"
fi
export DEVELOPER_DIR

exec python3 "$(dirname "$0")/probes.py" "$@"
