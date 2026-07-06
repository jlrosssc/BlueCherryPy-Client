#!/bin/bash
set -e

echo "=== BluecherryPy Client — macOS installer ==="

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install it from https://www.python.org/downloads/"
    exit 1
fi

PYVER=$(python3 -c "import sys; print(sys.version_info[:2] >= (3,11))")
if [ "$PYVER" = "False" ]; then
    echo "ERROR: Python 3.11 or later required."
    exit 1
fi

# Clone if not already inside the repo
if [ ! -f "main.py" ]; then
    git clone https://github.com/jlrosssc/BlueCherryPy-Client.git
    cd BlueCherryPy-Client
fi

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Dependencies
pip install --upgrade pip -q
pip install -r requirements.txt

# Launcher
chmod +x BluecherryPy.command

echo ""
echo "=== Install complete ==="
echo "To run:  source .venv/bin/activate && python3 main.py"
echo "Or double-click BluecherryPy.command in Finder."
echo ""

read -p "Launch now? [Y/n] " ans
if [[ "$ans" != "n" && "$ans" != "N" ]]; then
    python3 main.py
fi
