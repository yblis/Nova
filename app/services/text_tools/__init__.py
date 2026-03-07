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


def get_history(filter_type=None, limit=50):
    history = _load_history()
    if filter_type:
        history = [h for h in history if h.get("type") == filter_type]
    return history[:limit]


def get_history_item(item_id):
    history = _load_history()
    for item in history:
        if item.get("id") == item_id:
            return item
    return None


def clear_history():
    return _save_history([])


def delete_history_item(item_id):
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
    "get_history",
    "get_history_item",
    "clear_history",
    "delete_history_item",
]
