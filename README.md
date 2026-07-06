# BluecherryPy Client

A cross-platform desktop client for [Bluecherry DVR](https://www.bluecherrydvr.com/) servers, written in Python and PyQt6.

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

### 1 — Clone the repo

```bash
git clone https://github.com/jlrosssc/BlueCherryPy-Client.git
cd BlueCherryPy-Client
```

### 2 — Create a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

> **macOS note:** PyQt6 multimedia (used for recording playback) requires the
> `PyQt6-Qt6` and `PyQt6-sip` wheels, which are bundled with the `PyQt6` package.
> No extra steps needed.

### 4 — Run

```bash
python3 main.py
```

### macOS double-click launcher

Make `BluecherryPy.command` executable, then double-click it in Finder:

```bash
chmod +x BluecherryPy.command
```

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

## Dependencies

| Package | Purpose |
|---------|---------|
| `PyQt6` | UI framework, video playback |
| `requests` | HTTP streaming and API calls |
| `keyring` | Secure password storage |
| `urllib3` | SSL warning suppression |

`Pillow` and `lxml` are listed in requirements for optional future use; the core app does not require them at runtime.

## License

GPL-2.0 — same license as the Linux kernel.
