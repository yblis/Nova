
import json
import os
import time
import uuid
from typing import List, Dict, Optional

class ChatHistoryService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.history_file = os.path.join(data_dir, "chat_history.json")
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w') as f:
                json.dump({"sessions": []}, f)

    def _load(self) -> Dict:
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except:
            return {"sessions": []}

    def _save(self, data: Dict):
        with open(self.history_file, 'w') as f:
            json.dump(data, f)

    def list_sessions(self) -> List[Dict]:
        data = self._load()
        # Return summary of sessions (id, title, model, updated_at), sorted by pinned status then updated_at
        sessions = []
        for s in data["sessions"]:
            sessions.append({
                "id": s.get("id"),
                "title": s.get("title"),
                "model": s.get("model"),
                "updated_at": s.get("updated_at"),
                "created_at": s.get("created_at"),
                "is_pinned": s.get("is_pinned", False)
            })
            
        return sorted(
            sessions, 
            key=lambda x: (not x.get("is_pinned", False), -x.get("updated_at", 0))
        )

    def get_session(self, session_id: str) -> Optional[Dict]:
        data = self._load()
        for s in data["sessions"]:
            if s["id"] == session_id:
                return s
        return None

    def create_session(self, model: str, title: str = "New Chat") -> str:
        data = self._load()
        session_id = str(uuid.uuid4())
        new_session = {
            "id": session_id,
            "title": title,
            "model": model,
            "is_pinned": False,   # Initialize as not pinned
            "system_prompt": "",  # Pre-prompt système
            "model_config": {      # Configuration du modèle
                "temperature": 0.7,
                "num_ctx": 4096,
                "top_p": 0.9,
                "top_k": 40,
            },
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": []
        }
        data["sessions"].append(new_session)
        self._save(data)
        return session_id

    def add_message(self, session_id: str, role: str, content: str, thinking: str = None, images: list = None, extra_data: dict = None):
        data = self._load()
        for s in data["sessions"]:
            if s["id"] == session_id:
                msg = {
                    "role": role, 
                    "content": content,
                    "timestamp": time.time()
                }
                if thinking:
                    msg["thinking"] = thinking
                if images:
                    msg["images"] = images  # Store base64 image data
                if extra_data:
                    msg["extra_data"] = extra_data
                s["messages"].append(msg)
                s["updated_at"] = time.time()
                
                # Auto-update title if it's the first user message
                # Only do this fallback if auto_generate_title is disabled
                if role == "user" and len(s["messages"]) <= 2 and s["title"] == "New Chat":
                    try:
                        from .llm_config_service import is_auto_title_enabled
                        if not is_auto_title_enabled():
                            # Fallback: use truncated message
                            s["title"] = content[:30] + "..." if len(content) > 30 else content
                    except Exception:
                        # If we can't check, use fallback
                        s["title"] = content[:30] + "..." if len(content) > 30 else content
                    
                self._save(data)
                return
        raise ValueError("Session not found")

    def delete_session(self, session_id: str):
        data = self._load()
        initial_len = len(data["sessions"])
        data["sessions"] = [s for s in data["sessions"] if s["id"] != session_id]
        if len(data["sessions"]) < initial_len:
            self._save(data)



    def update_session_context(self, session_id: str, context: List[int]):
        data = self._load()
        for s in data["sessions"]:
            if s["id"] == session_id:
                s["latest_context"] = context
                self._save(data)
                return
        raise ValueError("Session not found")

    def update_session_settings(self, session_id: str, system_prompt: str = None, model_config: Dict = None, title: str = None):
        """Update session settings like system_prompt, model_config, or title"""
        data = self._load()
        for s in data["sessions"]:
            if s["id"] == session_id:
                if system_prompt is not None:
                    s["system_prompt"] = system_prompt
                if model_config is not None:
                    # Merge with existing config to allow partial updates
                    existing_config = s.get("model_config", {})
                    existing_config.update(model_config)
                    s["model_config"] = existing_config
                if title is not None:
                    s["title"] = title
                s["updated_at"] = time.time()
                self._save(data)
                return s
        raise ValueError("Session not found")

    def toggle_session_pin(self, session_id: str) -> bool:
        """Toggle the pinned status of a session. Returns new status."""
        data = self._load()
        for s in data["sessions"]:
            if s["id"] == session_id:
                current_status = s.get("is_pinned", False)
                s["is_pinned"] = not current_status
                # We don't update 'updated_at' when pinning so it doesn't jump to top if unpinned
                self._save(data)
                return s["is_pinned"]
        raise ValueError("Session not found")

    def delete_sessions(self, session_ids: List[str]) -> int:
        """Delete multiple sessions by their IDs. Returns count of deleted sessions."""
        data = self._load()
        initial_len = len(data["sessions"])
        data["sessions"] = [s for s in data["sessions"] if s["id"] not in session_ids]
        deleted_count = initial_len - len(data["sessions"])
        if deleted_count > 0:
            self._save(data)
        return deleted_count

    def delete_all_sessions(self) -> int:
        """Delete all sessions. Returns count of deleted sessions."""
        data = self._load()
        deleted_count = len(data["sessions"])
        if deleted_count > 0:
            data["sessions"] = []
            self._save(data)
        return deleted_count
