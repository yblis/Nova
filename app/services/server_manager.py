import json
import os
import uuid
from typing import List, Dict, Optional

class ServerManager:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self._ensure_data_file()

    def _ensure_data_file(self):
        if not os.path.exists(self.data_path):
            default_data = {
                "active_server_id": "default",
                "servers": [
                    {"id": "default", "name": "Localhost", "url": "http://localhost:11434"}
                ]
            }
            self._save_data(default_data)

    def _load_data(self) -> Dict:
        try:
            with open(self.data_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"active_server_id": None, "servers": []}

    def _save_data(self, data: Dict):
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        with open(self.data_path, 'w') as f:
            json.dump(data, f, indent=2)

    def get_servers(self) -> List[Dict]:
        data = self._load_data()
        return data.get("servers", [])

    def get_server(self, server_id: str) -> Optional[Dict]:
        servers = self.get_servers()
        for s in servers:
            if s["id"] == server_id:
                return s
        return None

    def add_server(self, name: str, url: str) -> Dict:
        data = self._load_data()
        new_id = str(uuid.uuid4())
        new_server = {"id": new_id, "name": name, "url": url}
        data["servers"].append(new_server)
        
        # If no active server, set this one
        if not data.get("active_server_id"):
            data["active_server_id"] = new_id
            
        self._save_data(data)
        return new_server

    def delete_server(self, server_id: str) -> bool:
        data = self._load_data()
        servers = data.get("servers", [])
        
        # Prevent deleting the last server if desired, or handle empty state logic
        # For now, allow deletion but random re-assignment if active was deleted
        
        new_servers = [s for s in servers if s["id"] != server_id]
        if len(new_servers) == len(servers):
            return False # ID not found
            
        data["servers"] = new_servers
        
        if data.get("active_server_id") == server_id:
            data["active_server_id"] = new_servers[0]["id"] if new_servers else None
            
        self._save_data(data)
        return True

    def set_active_server(self, server_id: str) -> bool:
        data = self._load_data()
        # Verify exists
        if not any(s["id"] == server_id for s in data.get("servers", [])):
            return False
            
        data["active_server_id"] = server_id
        self._save_data(data)
        return True

    def get_active_server(self) -> Optional[Dict]:
        data = self._load_data()
        active_id = data.get("active_server_id")
        if not active_id:
            # Fallback to first if exists
            servers = data.get("servers", [])
            if servers:
                return servers[0]
            return None
            
        for s in data.get("servers", []):
            if s["id"] == active_id:
                return s
        
        # ID pointing to non-existent server? Fallback
        servers = data.get("servers", [])
        if servers:
             # Auto-fix: update active ID
             data["active_server_id"] = servers[0]["id"]
             self._save_data(data)
             return servers[0]
             
        return None

    def update_server(self, server_id: str, name: str, url: str) -> Optional[Dict]:
        data = self._load_data()
        servers = data.get("servers", [])
        
        for s in servers:
            if s["id"] == server_id:
                s["name"] = name
                s["url"] = url
                self._save_data(data)
                return s
        return None

    def get_active_server_url(self) -> str:
        server = self.get_active_server()
        return server["url"] if server else "http://localhost:11434"
