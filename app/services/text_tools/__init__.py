from .redaction import (
    reformulate,
    translate,
    correct,
    generate_email,
    expand_text,
)

from .analysis import (
    extract_data,
    simplify_text,
    compare_decide,
    explain_eli5,
    generate_summary,
    convert_format,
)

from .technical import (
    generate_script,
    generate_mermaid,
    generate_regex,
    generate_prompt,
    parse_logs,
)

from .generators import (
    generate_documentation,
    generate_todolist,
    generate_flashcards,
)

from .everyday import (
    generate_recipe,
    generate_fitness,
    generate_admin_letter,
    generate_speech,
)

from ._shared import (
    _load_history,
    _save_history,
)


def _db_available() -> bool:
    try:
        from app.extensions import db
        db.session.execute(db.text("SELECT 1"))
        return True
    except Exception:
        return False


def get_history(filter_type=None, limit=50):
    if _db_available():
        try:
            from app.models.text_tool_history import TextToolHistory
            query = TextToolHistory.query.order_by(TextToolHistory.created_at.desc())
            if filter_type:
                query = query.filter_by(tool_type=filter_type)
            return [r.to_dict() for r in query.limit(limit).all()]
        except Exception:
            pass
    history = _load_history()
    if filter_type:
        history = [h for h in history if h.get("type") == filter_type]
    return history[:limit]


def get_history_item(item_id):
    if _db_available():
        try:
            from app.models.text_tool_history import TextToolHistory
            r = TextToolHistory.query.get(item_id)
            return r.to_dict() if r else None
        except Exception:
            pass
    history = _load_history()
    for item in history:
        if item.get("id") == item_id:
            return item
    return None


def clear_history():
    if _db_available():
        try:
            from app.extensions import db
            from app.models.text_tool_history import TextToolHistory
            TextToolHistory.query.delete()
            db.session.commit()
            return True
        except Exception:
            pass
    return _save_history([])


def delete_history_item(item_id):
    if _db_available():
        try:
            from app.extensions import db
            from app.models.text_tool_history import TextToolHistory
            r = TextToolHistory.query.get(item_id)
            if r:
                db.session.delete(r)
                db.session.commit()
                return True
            return False
        except Exception:
            pass
    history = _load_history()
    new_history = [h for h in history if h.get("id") != item_id]
    if len(new_history) < len(history):
        return _save_history(new_history)
    return False



__all__ = [
    "reformulate",
    "translate",
    "correct",
    "generate_email",
    "expand_text",
    "extract_data",
    "simplify_text",
    "compare_decide",
    "explain_eli5",
    "generate_summary",
    "convert_format",
    "generate_script",
    "generate_mermaid",
    "generate_regex",
    "generate_prompt",
    "generate_documentation",
    "generate_todolist",
    "generate_flashcards",
    "generate_recipe",
    "generate_fitness",
    "generate_admin_letter",
    "generate_speech",
    "parse_logs",
    "get_history",
    "get_history_item",
    "clear_history",
    "delete_history_item",
]
