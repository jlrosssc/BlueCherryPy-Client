#!/bin/bash
# Double-click this file to launch BluecherryPy.
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Locate python3 — Finder doesn't inherit the full shell PATH
PYTHON=""
for candidate in \
    python3 \
    "/opt/homebrew/Caskroom/miniconda/base/bin/python3" \
    "/opt/homebrew/Caskroom/miniforge/base/bin/python3" \
    "/opt/homebrew/Caskroom/anaconda/base/bin/python3" \
    "/opt/homebrew/bin/python3" \
    "$HOME/Library/Python/3.13/bin/python3" \
    "$HOME/Library/Python/3.12/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" \
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3" \
    /usr/local/bin/python3 \
    /usr/bin/python3; do
    if "$candidate" -c "import PyQt6" &>/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    osascript -e 'display alert "Python 3 not found" message "Install Python 3.10+ from python.org then try again."'
    exit 1
fi

exec "$PYTHON" main.py
