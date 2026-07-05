from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RecordingEvent:
    id: int
    device_id: Optional[int] = None
    time: Optional[int] = None
    level_id: Optional[str] = None
    type_id: Optional[str] = None
    length: Optional[int] = None
    archive: Optional[bool] = None
    media_id: Optional[int] = None
    details: Optional[str] = None
    media_url_string: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> RecordingEvent:
        return cls(
            id=int(d.get("id", 0)),
            device_id=int(d["device_id"]) if d.get("device_id") else None,
            time=int(d["time"]) if d.get("time") else None,
            level_id=d.get("level_id"),
            type_id=d.get("type_id"),
            length=int(d["length"]) if d.get("length") else None,
            archive=d.get("archive"),
            media_id=int(d["media_id"]) if d.get("media_id") else None,
            details=d.get("details"),
            media_url_string=d.get("media_url"),
        )

    @property
    def title(self) -> str:
        if self.details:
            return self.details
        return self.type_id or "Recording"

    @property
    def date(self) -> Optional[datetime]:
        return datetime.fromtimestamp(self.time) if self.time else None

    @property
    def duration_description(self) -> Optional[str]:
        if self.length is None:
            return None
        m, s = divmod(self.length, 60)
        return f"{m}m {s}s" if m else f"{s}s"

    def with_fallback_device_id(self, fallback: int) -> RecordingEvent:
        if self.device_id is not None:
            return self
        from dataclasses import replace
        return replace(self, device_id=fallback)
