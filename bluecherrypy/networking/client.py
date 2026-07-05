from __future__ import annotations
import json
import re
import tempfile
import os
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import xml.etree.ElementTree as ET
from bluecherrypy.models.server import Server
from bluecherrypy.models.device import Device
from bluecherrypy.models.recording import RecordingEvent


class BluecherryError(Exception):
    def __init__(self, message: str, code: str = "BC-ERR"):
        super().__init__(message)
        self.code = code


def _make_session(timeout: int = 20) -> requests.Session:
    session = requests.Session()
    session.verify = False  # Accept self-signed certs (standard for Bluecherry installs)
    adapter = HTTPAdapter(max_retries=Retry(total=1, backoff_factor=0.3))
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _looks_like_login_page(text: str, content_type: str) -> bool:
    if "text/html" not in content_type.lower():
        return False
    lower = text[:4096].lower()
    return "login" in lower or "password" in lower


class BluecherryClient:
    def __init__(self, server: Server):
        self.server = server
        self._session = _make_session()
        self._timeout = 20

    def connect(self) -> list[Device]:
        try:
            self._login()
        except BluecherryError:
            pass
        return self.fetch_devices()

    def _login(self):
        resp = self._session.post(
            self.server.login_url,
            data={"login": self.server.login, "password": self.server.password, "from_client": "true"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._timeout,
        )
        if not resp.ok:
            raise BluecherryError(f"HTTP {resp.status_code}", "BC-AUTH-002")
        text = resp.text[:4096].lower()
        if '"success":false' in text or "wrong login" in text or "wrong password" in text:
            raise BluecherryError("Authentication failed.", "BC-AUTH-001")

    def fetch_devices(self) -> list[Device]:
        for use_basic in (False, True):
            devices = self._request_devices(use_basic)
            if devices is not None:
                return sorted(devices, key=lambda d: d.name.lower())
        raise BluecherryError("Authentication failed.", "BC-AUTH-001")

    def _request_devices(self, use_basic: bool) -> Optional[list[Device]]:
        headers = {}
        if use_basic:
            headers["Authorization"] = self.server.authorization_header
        try:
            resp = self._session.get(self.server.devices_url, headers=headers, timeout=self._timeout)
        except requests.RequestException as e:
            raise BluecherryError(str(e), "BC-NET-000")
        if resp.status_code in (401, 403):
            return None
        if not resp.ok:
            raise BluecherryError(f"HTTP {resp.status_code}", f"BC-HTTP-{resp.status_code}")
        text = resp.text
        if "<devices" not in text.lower() and "<device" not in text.lower():
            return None
        return _parse_devices_xml(text)

    def snapshot(self, device_id: int) -> bytes:
        resp = self._session.get(
            self.server.jpeg_url(device_id),
            headers={"Authorization": self.server.authorization_header},
            timeout=self._timeout,
        )
        if not resp.ok:
            raise BluecherryError(f"HTTP {resp.status_code}", f"BC-HTTP-{resp.status_code}")
        return resp.content

    def send_ptz(self, device_id: int, command: str = "move", pan: str = None,
                 tilt: str = None, zoom: str = None, speed: int = 5, duration: int = 250):
        try:
            self._login()
        except BluecherryError:
            pass
        url = self.server.ptz_url(device_id, command, pan, tilt, zoom, speed, duration)
        resp = self._session.get(url, headers={"Authorization": self.server.authorization_header},
                                 timeout=self._timeout)
        if not resp.ok:
            raise BluecherryError(f"HTTP {resp.status_code}")

    def fetch_recordings(self, device_id: int, limit: int = 500) -> list[RecordingEvent]:
        # Establish cookie session; continue even if login fails — Basic auth header is also sent
        try:
            self._login()
        except BluecherryError:
            pass
        failures = []
        for url in (
            self.server.ajax_events_url(device_id, limit),
            self.server.events_url(device_id, limit),
        ):
            try:
                recs = self._fetch_legacy_recordings(url)
                recs = _filter_by_device(recs, device_id)
                if recs is not None:  # empty list is valid (no recordings), not a failure
                    return recs
            except BluecherryError as e:
                if _is_auth_error(e):
                    raise
                failures.append(f"{url}: {e}")
        try:
            recs = self._fetch_beta_recordings(device_id, limit)
            return _filter_by_device(recs, device_id)
        except BluecherryError as e:
            if _is_auth_error(e):
                raise
            failures.append(str(e))
            raise BluecherryError(f"Could not read recordings. {'; '.join(failures)}", "BC-REC-001")

    def _fetch_legacy_recordings(self, url: str) -> list[RecordingEvent]:
        resp = self._session.get(url, headers={"Authorization": self.server.authorization_header},
                                 timeout=self._timeout)
        if resp.status_code in (401, 403) or 300 <= resp.status_code < 400:
            raise BluecherryError("Authentication failed.", "BC-AUTH-001")
        if not resp.ok:
            raise BluecherryError(f"HTTP {resp.status_code}")
        ct = resp.headers.get("Content-Type", "")
        if _looks_like_login_page(resp.text, ct):
            raise BluecherryError("Authentication failed.", "BC-AUTH-001")
        # Try JSON first (ajax endpoint), fall back to Atom XML
        try:
            data = resp.json()
            entries = data.get("entry", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            results = []
            for entry in entries:
                content = entry.get("content", {}) or {}
                media_id = content.get("media_id")
                if media_id is None:
                    continue
                raw_id = entry.get("id", "")
                event_id = int(raw_id.split("=")[-1]) if "=" in str(raw_id) else media_id
                cat = entry.get("category", {}) or {}
                parts = cat.get("term", "").split("/")
                results.append(RecordingEvent(
                    id=event_id,
                    time=None,
                    level_id=parts[1] if len(parts) > 1 else None,
                    device_id=int(parts[0]) if parts and parts[0].isdigit() else None,
                    type_id=parts[2] if len(parts) > 2 else None,
                    length=content.get("media_duration"),
                    media_id=media_id,
                    details=entry.get("title"),
                    media_url_string=content.get("content"),
                ))
            return results
        except (ValueError, AttributeError):
            pass
        # Atom XML path
        xml_results = _parse_legacy_xml(resp.text)
        if not xml_results and resp.text.strip():
            # Got a response but parsed nothing — log the start so the error is diagnosable
            preview = resp.text[:200].replace('\n', ' ')
            raise BluecherryError(f"Unrecognised events format: {preview}", "BC-PARSE-001")
        return xml_results

    def _fetch_beta_recordings(self, device_id: int, limit: int) -> list[RecordingEvent]:
        resp = self._session.get(
            self.server.beta_events_url(device_id, limit),
            headers={"Authorization": self.server.authorization_header},
            timeout=self._timeout,
        )
        if resp.status_code in (401, 403) or 300 <= resp.status_code < 400:
            raise BluecherryError("Authentication failed.", "BC-AUTH-001")
        if not resp.ok:
            raise BluecherryError(f"HTTP {resp.status_code}")
        data = resp.json()
        recs = [RecordingEvent.from_dict(r) for r in data if r.get("media_id")]
        return sorted(recs, key=lambda r: r.time or 0, reverse=True)

    def download_recording(self, recording: RecordingEvent) -> str:
        try:
            self._login()
        except BluecherryError:
            pass
        candidates = self._download_candidates(recording)
        if not candidates:
            raise BluecherryError("This event has no media file.", "BC-MEDIA-001")
        return self._download_first_available(candidates, recording)

    def _download_candidates(self, recording: RecordingEvent) -> list[str]:
        candidates = []
        if recording.media_url_string:
            candidates.append(self._resolve_media_url(recording.media_url_string))
        if recording.media_id:
            candidates += [
                self.server.stream_mp4_url(recording.media_id),
                self.server.download_mkv_url(recording.media_id),
                self.server.media_request_url(recording.media_id),
                self.server.beta_media_url(recording.media_id),
            ]
        return [c for c in candidates if c]

    def _resolve_media_url(self, url_string: str) -> Optional[str]:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url_string.strip())
        if not parsed.path:
            return None
        base = urlparse(self.server._base_url())
        return urlunparse((base.scheme, base.netloc, parsed.path, "", parsed.query, ""))

    def _download_first_available(self, candidates: list[str], recording: RecordingEvent) -> str:
        fname = f"bluecherry-{recording.media_id or recording.id}"
        last_error = None
        for url in dict.fromkeys(candidates):
            try:
                return self._download_media(url, fname)
            except BluecherryError as e:
                last_error = e
        raise last_error or BluecherryError("Could not download recording.", "BC-MEDIA-001")

    def _download_media(self, url: str, filename: str) -> str:
        headers = {
            "Authorization": self.server.authorization_header,
            "Accept": "video/mp4,video/mpeg,application/octet-stream,*/*",
        }
        resp = self._session.get(url, headers=headers, stream=True, timeout=60)
        if not resp.ok:
            raise BluecherryError(f"HTTP {resp.status_code}")
        ct = resp.headers.get("Content-Type", "").lower()
        if "text/html" in ct or "application/json" in ct:
            raise BluecherryError("Server returned login page instead of media.")
        ext = "mkv" if "mkv" in url else ("mpeg" if "mpeg" in ct else "mp4")
        path = os.path.join(tempfile.gettempdir(), f"{filename}.{ext}")
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        if os.path.getsize(path) == 0:
            raise BluecherryError("Server returned empty file.")
        return path


def _parse_devices_xml(text: str) -> list[Device]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    devices = []
    for elem in root.iter():
        if elem.tag.lower() in ("device", "camera"):
            attrs = {**elem.attrib}
            for child in elem:
                attrs[child.tag] = child.text or ""
            if attrs.get("id"):
                devices.append(Device.from_attributes(attrs))
    return devices


def _strip_ns(root):
    """Strip XML namespace prefixes so tags can be matched by local name."""
    import re
    for elem in root.iter():
        elem.tag = re.sub(r'\{[^}]*\}', '', elem.tag)
    return root


def _parse_legacy_xml(text: str) -> list[RecordingEvent]:
    try:
        root = _strip_ns(ET.fromstring(text))
    except ET.ParseError:
        return []
    results = []
    for entry in root.findall(".//entry"):
        content_el = entry.find("content")
        if content_el is None:
            continue
        media_id_str = content_el.get("media_id") or content_el.get("mediaID")
        if not media_id_str:
            continue
        media_id = int(media_id_str)
        id_el = entry.find("id")
        raw_id = id_el.text if id_el is not None else ""
        event_id = int(raw_id.split("=")[-1]) if raw_id and "=" in raw_id else media_id
        cat_el = entry.find("category")
        term = cat_el.get("term", "") if cat_el is not None else ""
        parts = term.split("/")
        title_el = entry.find("title")
        results.append(RecordingEvent(
            id=event_id, media_id=media_id,
            device_id=int(parts[0]) if parts and parts[0].isdigit() else None,
            level_id=parts[1] if len(parts) > 1 else None,
            type_id=parts[2] if len(parts) > 2 else None,
            details=title_el.text if title_el is not None else None,
            media_url_string=content_el.text,
        ))
    return results


def _filter_by_device(recs: list[RecordingEvent], device_id: int) -> list[RecordingEvent]:
    result = []
    for r in recs:
        if r.device_id is not None and r.device_id != device_id:
            continue
        result.append(r.with_fallback_device_id(device_id))
    return result


def _is_auth_error(e: BluecherryError) -> bool:
    return "AUTH" in e.code or "login" in str(e).lower()
