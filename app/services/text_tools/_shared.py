import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import current_app


def _get_llm_client():
    from ..llm_clients import get_active_client
    from ..llm_error_handler import LLMError

    try:
        client = get_active_client()
        if client:
            return client
    except LLMError:
        pass

    from ..ollama_client import OllamaClient
    from ...utils import get_effective_ollama_base_url
    return OllamaClient(
        base_url=get_effective_ollama_base_url(),
        connect_timeout=current_app.config.get("HTTP_CONNECT_TIMEOUT", 10),
        read_timeout=current_app.config.get("HTTP_READ_TIMEOUT", 120),
    )


def _get_history_path() -> str:
    try:
        return os.path.join(current_app.root_path, "data", "text_tools_history.json")
    except RuntimeError:
        return os.path.join(os.path.dirname(__file__), "..", "..", "data", "text_tools_history.json")


def _load_history() -> List[Dict[str, Any]]:
    history_path = _get_history_path()
    try:
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_history(history: List[Dict[str, Any]]) -> bool:
    history_path = _get_history_path()
    try:
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f"Failed to save text tools history: {e}")
        except RuntimeError:
            pass
        return False


def _add_to_history(entry: Dict[str, Any]) -> str:
    history = _load_history()
    entry_id = str(uuid.uuid4())
    entry["id"] = entry_id
    entry["created_at"] = datetime.utcnow().isoformat()
    history.insert(0, entry)
    history = history[:100]
    _save_history(history)
    return entry_id
