from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse, urlencode, urlunparse
import base64


class StreamProtocol(Enum):
    MJPEG = "mjpeg"
    JPEG_POLLING = "jpegPolling"

    @property
    def label(self):
        return "MJPEG Stream (direct)" if self == StreamProtocol.MJPEG else "JPEG Refresh (tunnel)"


@dataclass
class Server:
    name: str
    host: str
    login: str
    password: str = ""
    port: int = 7001
    rtsp_port: int = 7002
    use_ssl: bool = True
    stream_protocol: StreamProtocol = StreamProtocol.MJPEG
    local_host: str = ""
    local_port: int = 7001
    local_use_ssl: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def _base_url(self) -> str:
        scheme = "https" if self.use_ssl else "http"
        return f"{scheme}://{self.host}:{self.port}"

    def _url(self, path: str, params: dict = None) -> str:
        base = self._base_url()
        url = f"{base}{path}"
        if params:
            url += "?" + urlencode({k: v for k, v in params.items() if v is not None})
        return url

    @property
    def authorization_header(self) -> str:
        raw = f"{self.login}:{self.password}"
        encoded = base64.b64encode(raw.encode()).decode()
        return f"Basic {encoded}"

    @property
    def login_url(self) -> str:
        return self._url("/ajax/loginapp.php", {
            "login": self.login, "password": self.password, "from_client": "true"
        })

    @property
    def devices_url(self) -> str:
        return self._url("/ajax/devices.php", {"XML": "true", "short": "true"})

    def events_url(self, device_id: int, limit: int = 500) -> str:
        return self._url("/events/", {"XML": "1", "device_id": device_id, "limit": limit})

    def ajax_events_url(self, device_id: int, limit: int = 500) -> str:
        return self._url("/ajax/events.php", {"XML": "1", "device_id": device_id, "limit": limit})

    def beta_events_url(self, device_id: int, limit: int = 500) -> str:
        return self._url("/events", {"device": device_id, "limit": limit})

    def mjpeg_url(self, device_id: int) -> str:
        return self._url("/media/mjpeg.php", {"multipart": "true", "id": device_id})

    def jpeg_url(self, device_id: int) -> str:
        return self._url("/media/mjpeg.php", {"id": device_id})

    def stream_mp4_url(self, media_id: int) -> str:
        return self._url("/media/stream-mp4", {"id": media_id})

    def download_mkv_url(self, media_id: int) -> str:
        return self._url(f"/playback/download-mkv/{media_id}")

    def media_request_url(self, media_id: int) -> str:
        return self._url("/media/request.php", {"id": media_id})

    def beta_media_url(self, media_id: int) -> str:
        return self._url(f"/media/{media_id}")

    def media_screenshot_url(self, media_id: int) -> str:
        return self._url("/media/request.php", {"mode": "screenshot", "id": media_id})

    def ptz_url(self, device_id: int, command: str, pan: str = None,
                tilt: str = None, zoom: str = None, speed: int = 5, duration: int = 250) -> str:
        params = {"id": device_id, "command": command,
                  "panspeed": speed, "tiltspeed": speed, "duration": duration}
        if pan:
            params["pan"] = pan
        if tilt:
            params["tilt"] = tilt
        if zoom:
            params["zoom"] = zoom
        return self._url("/media/ptz.php", params)

    def as_local(self) -> "Server":
        """Return a copy using the local_host address with MJPEG forced (LAN is fast)."""
        from dataclasses import replace
        return replace(self,
                       host=self.local_host,
                       port=self.local_port,
                       use_ssl=self.local_use_ssl,
                       stream_protocol=StreamProtocol.MJPEG)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "host": self.host,
            "port": self.port, "rtsp_port": self.rtsp_port, "login": self.login,
            "use_ssl": self.use_ssl, "stream_protocol": self.stream_protocol.value,
            "local_host": self.local_host, "local_port": self.local_port,
            "local_use_ssl": self.local_use_ssl,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Server:
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=d["name"], host=d["host"], login=d["login"],
            port=d.get("port", 7001), rtsp_port=d.get("rtsp_port", 7002),
            use_ssl=d.get("use_ssl", True),
            stream_protocol=StreamProtocol(d.get("stream_protocol", "mjpeg")),
            local_host=d.get("local_host", ""), local_port=d.get("local_port", 7001),
            local_use_ssl=d.get("local_use_ssl", True),
        )
