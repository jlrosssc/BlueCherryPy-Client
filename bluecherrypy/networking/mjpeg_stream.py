from __future__ import annotations
import socket
import threading
import time
from typing import Callable, Optional
import requests
from bluecherrypy.models.server import Server, StreamProtocol


# ── Local-network probe ────────────────────────────────────────────────────────

def _probe_local(server: Server, timeout: float = 1.0) -> bool:
    """TCP-connect to server.local_host to check if we're on the LAN."""
    if not server.local_host:
        return False
    try:
        with socket.create_connection((server.local_host, server.local_port), timeout=timeout):
            return True
    except (socket.timeout, socket.error, OSError):
        return False


def _resolve_active_server(server: Server) -> Server:
    """
    Auto-select local vs remote address and stream protocol:
    - If local_host is set and reachable (LAN) → use local address + MJPEG
    - Otherwise → use configured host + configured stream_protocol
    """
    if server.local_host and _probe_local(server):
        return server.as_local()
    return server


# ── Stream factory ─────────────────────────────────────────────────────────────

def create_stream(server: Server, device_id: int,
                  on_frame: Callable[[bytes], None],
                  on_error: Callable[[str], None]) -> "MJPEGStream | JPEGPollingStream":
    """
    Probe local network, pick the right server address and protocol, return the
    appropriate stream object. Called from inside a background thread.
    """
    active = _resolve_active_server(server)
    if active.stream_protocol == StreamProtocol.JPEG_POLLING:
        return JPEGPollingStream(active, device_id, on_frame, on_error)
    return MJPEGStream(active, device_id, on_frame, on_error)


# ── MJPEG streaming ────────────────────────────────────────────────────────────

class MJPEGStream:
    """Multipart MJPEG — best on local LAN; may stall through reverse proxies."""

    def __init__(self, server: Server, device_id: int,
                 on_frame: Callable[[bytes], None],
                 on_error: Callable[[str], None]):
        self.server = server
        self.device_id = device_id
        self.on_frame = on_frame
        self.on_error = on_error
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        url = self.server.mjpeg_url(self.device_id)
        headers = {"Authorization": self.server.authorization_header}
        session = requests.Session()
        session.verify = False
        try:
            with session.get(url, headers=headers, stream=True, timeout=20) as resp:
                if not resp.ok:
                    self.on_error(f"HTTP {resp.status_code}")
                    return
                ct = resp.headers.get("Content-Type", "").lower()
                if "text/html" in ct:
                    self.on_error("Authentication required.")
                    return
                self._read_mjpeg(resp)
        except requests.RequestException as e:
            if not self._stop_event.is_set():
                self.on_error(str(e))
        finally:
            session.close()

    def _read_mjpeg(self, resp):
        SOI = b"\xff\xd8"
        EOI = b"\xff\xd9"
        buf = b""
        for chunk in resp.iter_content(chunk_size=8192):
            if self._stop_event.is_set():
                return
            buf += chunk
            while True:
                start = buf.find(SOI)
                if start == -1:
                    buf = buf[-1:] if buf else b""
                    break
                end = buf.find(EOI, start + 2)
                if end == -1:
                    buf = buf[start:]
                    break
                self.on_frame(buf[start:end + 2])
                buf = buf[end + 2:]


# ── JPEG polling ───────────────────────────────────────────────────────────────

class JPEGPollingStream:
    """
    Fetches a single JPEG snapshot repeatedly.
    Works reliably through reverse proxies and VPN tunnels where MJPEG stalls.
    """

    def __init__(self, server: Server, device_id: int,
                 on_frame: Callable[[bytes], None],
                 on_error: Callable[[str], None],
                 fps: float = 1.0):
        self.server = server
        self.device_id = device_id
        self.on_frame = on_frame
        self.on_error = on_error
        self._interval = 1.0 / max(fps, 0.1)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        url = self.server.jpeg_url(self.device_id)
        headers = {"Authorization": self.server.authorization_header}
        session = requests.Session()
        session.verify = False
        consecutive_errors = 0

        while not self._stop_event.is_set():
            t0 = time.monotonic()
            try:
                r = session.get(url, headers=headers, timeout=10)
                if self._stop_event.is_set():
                    break
                ct = r.headers.get("Content-Type", "").lower()
                if "text/html" in ct:
                    self.on_error("Authentication required.")
                    break
                if r.ok and r.content:
                    self.on_frame(r.content)
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    if consecutive_errors >= 5:
                        self.on_error(f"HTTP {r.status_code}")
                        break
            except requests.RequestException as e:
                if self._stop_event.is_set():
                    break
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    self.on_error(str(e))
                    break

            elapsed = time.monotonic() - t0
            wait = max(0.0, self._interval - elapsed)
            self._stop_event.wait(wait)

        session.close()
