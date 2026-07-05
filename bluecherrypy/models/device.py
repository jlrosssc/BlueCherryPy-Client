from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class Device:
    id: int
    name: str
    online: bool = True
    resolution_x: Optional[int] = None
    resolution_y: Optional[int] = None
    has_ptz: bool = False

    @classmethod
    def from_attributes(cls, attrs: dict) -> Device:
        dev_id = int(attrs.get("id", 0))
        name = attrs.get("device_name") or attrs.get("device") or attrs.get("name") or f"Camera {dev_id}"
        status = attrs.get("status", attrs.get("online", "")).strip().lower()
        online = not status or status in ("ok", "online", "true", "1")
        return cls(
            id=dev_id, name=name, online=online,
            resolution_x=int(attrs["resolutionX"]) if attrs.get("resolutionX") else None,
            resolution_y=int(attrs["resolutionY"]) if attrs.get("resolutionY") else None,
            has_ptz="ptz_control_protocol" in attrs,
        )

    @property
    def resolution(self) -> Optional[str]:
        if self.resolution_x and self.resolution_y:
            return f"{self.resolution_x}×{self.resolution_y}"
        return None
