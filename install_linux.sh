#!/bin/bash
set -e

echo "=== BluecherryPy Client — Linux installer ==="

# Detect distro
if command -v apt &>/dev/null; then
    DISTRO="debian"
elif command -v dnf &>/dev/null; then
    DISTRO="fedora"
elif command -v yum &>/dev/null; then
    DISTRO="rhel"
else
    echo "WARNING: Could not detect package manager. Install system deps manually if needed."
    DISTRO="unknown"
fi

# System dependencies
if [ "$DISTRO" = "debian" ]; then
    echo "Installing system libraries (apt)..."
    sudo apt install -y \
        python3-dev python3-venv python3-pip \
        libglib2.0-0 libegl1 \
        libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
        libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
        libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 \
        libxkbcommon-x11-0 \
        ffmpeg gnome-keyring

elif [ "$DISTRO" = "fedora" ] || [ "$DISTRO" = "rhel" ]; then
    echo "Installing system libraries (dnf)..."
    sudo dnf install -y \
        python3-devel python3-pip \
        mesa-libEGL \
        xcb-util-cursor xcb-util-image xcb-util-keysyms \
        xcb-util-renderutil xcb-util-wm \
        libxkbcommon-x11 \
        ffmpeg gnome-keyring
fi

# Check Python version
if ! python3 -c "import sys; assert sys.version_info >= (3,11)" 2>/dev/null; then
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

echo ""
echo "=== Install complete ==="
echo "To run:  source .venv/bin/activate && python3 main.py"
echo ""

read -p "Launch now? [Y/n] " ans
if [[ "$ans" != "n" && "$ans" != "N" ]]; then
    python3 main.py
fi
