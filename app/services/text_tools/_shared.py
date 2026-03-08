import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from flask import current_app


def _get_llm_client(model: str = None):
    from ..model_router import get_client_for_model
    return get_client_for_model(model)


# ── Utilitaires backend ────────────────────────────────────────────────────────

def _db_available() -> bool:
    """Vérifie si SQLAlchemy+PostgreSQL est disponible."""
    try:
        from ...extensions import db
        db.session.execute(db.text("SELECT 1"))
        return True
    except Exception:
        return False


def _get_history_path() -> str:
    try:
        return os.path.join(current_app.root_path, "data", "text_tools_history.json")
    except RuntimeError:
        return os.path.join(os.path.dirname(__file__), "..", "..", "data", "text_tools_history.json")


def _load_history_json() -> List[Dict[str, Any]]:
    history_path = _get_history_path()
    try:
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_history_json(history: List[Dict[str, Any]]) -> bool:
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
    """Ajoute une entrée à l'historique (SQLAlchemy si dispo, JSON sinon)."""
    entry_id = str(uuid.uuid4())
    if _db_available():
        try:
            from ...extensions import db
            from ...models.text_tool_history import TextToolHistory
            record = TextToolHistory(
                id=entry_id,
                tool_type=entry.get("type", "unknown"),
                input_text=entry.get("input", ""),
                output_text=entry.get("output", ""),
                model_used=entry.get("model", ""),
            )
            record.set_options(entry.get("options", {}))
            db.session.add(record)
            db.session.commit()
            return entry_id
        except Exception:
            pass  # Fallback JSON ci-dessous

    # Fallback JSON
    history = _load_history_json()
    entry["id"] = entry_id
    entry["created_at"] = datetime.now(timezone.utc).isoformat()
    history.insert(0, entry)
    history = history[:100]
    _save_history_json(history)
    return entry_id


def _load_history(filter_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Charge l'historique (SQLAlchemy si dispo, JSON sinon)."""
    if _db_available():
        try:
            from ...models.text_tool_history import TextToolHistory
            query = TextToolHistory.query.order_by(TextToolHistory.created_at.desc())
            if filter_type:
                query = query.filter_by(tool_type=filter_type)
            records = query.limit(limit).all()
            return [r.to_dict() for r in records]
        except Exception:
            pass

    return _load_history_json()


def _save_history(history: List[Dict[str, Any]]) -> bool:
    """Sauvegarde l'historique (JSON uniquement — utilisé pour clear/delete)."""
    if _db_available():
        # En mode DB, clear se fait via les routes qui appellent les bonnes méthodes
        return True
    return _save_history_json(history)
