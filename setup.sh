#!/usr/bin/env bash
# Tony's Sysadmin Swiss Army Knife — Linux / macOS launcher
set -e

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" -c "import sys; print(sys.version_info >= (3,9))" 2>/dev/null)
        if [ "$VER" = "True" ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[!] Python 3.9+ is required. Install it from https://python.org"
    exit 1
fi

echo "[*] Python: $($PYTHON --version)"
echo "[*] Installing / upgrading dependencies…"

PIP_FLAGS="--quiet --upgrade --no-warn-script-location"
$PYTHON -m pip install $PIP_FLAGS rich prompt_toolkit psutil requests 2>/dev/null \
    || $PYTHON -m pip install $PIP_FLAGS --user rich prompt_toolkit psutil requests 2>/dev/null \
    || $PYTHON -m pip install $PIP_FLAGS --user --break-system-packages rich prompt_toolkit psutil requests

echo "[*] Launching Tony's Sysadmin Swiss Army Knife…"
exec "$PYTHON" "$(dirname "$0")/sysknife.py" "$@"
