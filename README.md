# BluecherryPy Client

A cross-platform desktop client for [Bluecherry DVR](https://www.bluecherrydvr.com/) servers, written in Python and PyQt6.

> Server source: [github.com/bluecherrydvr](https://github.com/bluecherrydvr)

## Features

- **Live view** — MJPEG streaming or JPEG polling (auto-selected based on network)
- **Zoom & pan** — scroll wheel to zoom, drag to pan in any camera window
- **Auto LAN detection** — switches between local address (MJPEG) and remote/tunnel (JPEG) automatically
- **Recordings browser** — thumbnail grid with camera and time filters (1h / 4h / 8h / Today / 7d / 30d)
- **Playback** — select a recording and press ▶ Play to watch it in the built-in player
- **Download** — save recordings to disk via 💾 Download or right-click context menu
- **PTZ support** — pan/tilt/zoom controls for compatible cameras
- **Dark UI** — Fusion style with a dark palette, readable on all platforms
- **Multiple servers** — add as many Bluecherry servers as you like; credentials stored in the system keychain

## Requirements

- Python 3.11 or later
- macOS, Linux, or Windows
- A running Bluecherry DVR server

## Install

### One-line install scripts

Copy and paste the command for your platform into a terminal:

**macOS**
```bash
git clone https://github.com/jlrosssc/BlueCherryPy-Client.git && cd BlueCherryPy-Client && bash install_macos.sh
```

**Linux (Ubuntu / Debian / Fedora)**
```bash
git clone https://github.com/jlrosssc/BlueCherryPy-Client.git && cd BlueCherryPy-Client && bash install_linux.sh
```

**Windows** — open Command Prompt and run:
```bat
git clone https://github.com/jlrosssc/BlueCherryPy-Client.git && cd BlueCherryPy-Client && install_windows.bat
```

Each script installs system dependencies, creates a virtual environment, installs Python packages, and offers to launch the app.

---

### Manual install

### 1 — Clone the repo

```bash
git clone https://github.com/jlrosssc/BlueCherryPy-Client.git
cd BlueCherryPy-Client
```

### 2 — Create a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows (Command Prompt)
# .venv\Scripts\Activate.ps1   # Windows (PowerShell)
```

### 3 — Install platform dependencies

#### macOS
No extra steps. All dependencies are bundled with the pip packages.

#### Linux (Ubuntu / Debian)

Install required system libraries before running `pip install`:

```bash
sudo apt install -y \
    python3-dev \
    libglib2.0-0 \
    libegl1 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    ffmpeg
```

For the system keychain (password storage) on Linux, install a secrets backend:

```bash
sudo apt install -y gnome-keyring
# or, for headless/minimal systems:
pip install keyrings.alt
```

#### Linux (Fedora / RHEL)

```bash
sudo dnf install -y \
    python3-devel \
    mesa-libEGL \
    xcb-util-cursor \
    xcb-util-image \
    xcb-util-keysyms \
    xcb-util-renderutil \
    xcb-util-wm \
    libxkbcommon-x11 \
    ffmpeg
```

#### Windows

No extra system packages needed. Python 3.11+ from [python.org](https://python.org) includes everything required.

> If pip complains about missing Visual C++ during install, download the
> [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).

### 4 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### 5 — Run

```bash
# macOS / Linux
python3 main.py

# Windows
python main.py
```

### macOS — double-click launcher

Make `BluecherryPy.command` executable once, then double-click it in Finder any time:

```bash
chmod +x BluecherryPy.command
```

### Windows — desktop shortcut

Create a `.bat` file next to `main.py` with this content:

```bat
@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe main.py
```

Double-click the `.bat` file to launch without a terminal window staying open.

---

## First-time setup

1. Click **Add Server** in the sidebar.
2. Enter your server's hostname/IP, port (default 7001), username, and password.
3. Optionally add a **Local address** (LAN IP) — the app will auto-switch to it when you're on the same network.
4. Click **Connect**.

## Keyboard & mouse

| Action | How |
|--------|-----|
| Zoom in live view | Scroll wheel |
| Pan in live view | Click and drag |
| Reset zoom | Toolbar → Reset Zoom |
| Play recording | Select it, press ▶ Play |
| Download recording | Select it, press 💾 Download — or right-click |
| Open in system player | ⤴ button in the player controls |

## Troubleshooting

**Linux: app won't start / "xcb" error**
Run `pip install pyqt6 --force-reinstall` and make sure the `libxcb-*` packages above are installed.

**Linux: passwords not saved between sessions**
Install `gnome-keyring` or run `pip install keyrings.alt` for a file-based fallback.

**Linux: no audio or video playback in recordings**
Install `ffmpeg` via your package manager. PyQt6 multimedia uses FFmpeg as its backend on Linux.

**Windows: `python3` not found**
Use `python` instead of `python3` — Windows installs it as `python`.

**Windows: SSL errors connecting to server**
The app suppresses self-signed certificate warnings by default. If you still get SSL errors, add your server's certificate to the Windows certificate store.

## Dependencies

| Package | Purpose |
|---------|---------|
| `PyQt6` | UI framework, video playback |
| `requests` | HTTP streaming and API calls |
| `keyring` | Secure password storage |
| `urllib3` | SSL warning suppression |

`Pillow` and `lxml` are listed in requirements for optional future use; the core app does not require them at runtime.

## License

GPL-3.0-or-later. See `LICENSE`.

## Third-Party Licenses

This app depends on PyQt6 and other third-party packages, each under its
own license. See `THIRD_PARTY_LICENSES.md`.
