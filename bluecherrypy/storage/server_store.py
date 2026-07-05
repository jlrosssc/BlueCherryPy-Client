from __future__ import annotations
import json
import os
from typing import Optional
import keyring
from bluecherrypy.models.server import Server

_SERVICE = "com.bluecherrypy"
_CONFIG_PATH = os.path.expanduser("~/.config/bluecherrypy/servers.json")


class ServerStore:
    def __init__(self):
        self.servers: list[Server] = []
        self.default_server_id: Optional[str] = None
        self._load()

    def add(self, server: Server):
        self.servers.append(server)
        keyring.set_password(_SERVICE, server.id, server.password)
        self._save()

    def update(self, server: Server):
        for i, s in enumerate(self.servers):
            if s.id == server.id:
                self.servers[i] = server
                keyring.set_password(_SERVICE, server.id, server.password)
                self._save()
                return

    def remove(self, server: Server):
        self.servers = [s for s in self.servers if s.id != server.id]
        try:
            keyring.delete_password(_SERVICE, server.id)
        except Exception:
            pass
        if self.default_server_id == server.id:
            self.default_server_id = None
        self._save()

    def set_default(self, server: Optional[Server]):
        self.default_server_id = server.id if server else None
        self._save()

    def is_default(self, server: Server) -> bool:
        return self.default_server_id == server.id

    def _save(self):
        os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
        data = {
            "servers": [s.to_dict() for s in self.servers],
            "default_server_id": self.default_server_id,
        }
        with open(_CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        if not os.path.exists(_CONFIG_PATH):
            return
        try:
            with open(_CONFIG_PATH) as f:
                data = json.load(f)
            self.default_server_id = data.get("default_server_id")
            for d in data.get("servers", []):
                server = Server.from_dict(d)
                try:
                    server.password = keyring.get_password(_SERVICE, server.id) or ""
                except Exception:
                    server.password = ""
                self.servers.append(server)
        except (json.JSONDecodeError, KeyError):
            self.servers = []
