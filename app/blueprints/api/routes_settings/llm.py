from flask import jsonify, request
from . import api_settings_bp


@api_settings_bp.get("/llm/config")
def get_llm_config():
    """Récupère la configuration LLM par défaut."""
    from ....services.llm_config_service import get_config
    config = get_config()
    return jsonify({
        "default_system_prompt": config.get("default_system_prompt", ""),
        "temperature": config.get("temperature", 0.7),
        "top_p": config.get("top_p", 0.9),
        "top_k": config.get("top_k", 40),
        "repeat_penalty": config.get("repeat_penalty", 1.1),
        "num_ctx": config.get("num_ctx", 4096),
        "auto_generate_title": config.get("auto_generate_title", True)
    })


@api_settings_bp.post("/llm/config")
def set_llm_config():
    """Configure les paramètres LLM par défaut."""
    from ....services.llm_config_service import set_config
    data = request.get_json(silent=True) or {}

    validators = {
        "temperature": (float, 0, 2),
        "top_p": (float, 0, 1),
        "top_k": (int, 1, 100),
        "repeat_penalty": (float, 1, 2),
        "num_ctx": (int, 2048, 128000),
    }
    for key, (cast, lo, hi) in validators.items():
        if key in data:
            try:
                val = cast(data[key])
                if not (lo <= val <= hi):
                    return jsonify({"error": f"{key} doit être entre {lo} et {hi}"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": f"{key} invalide"}), 400

    success = set_config(data)
    if not success:
        return jsonify({"error": "Échec de la sauvegarde"}), 500

    return jsonify({"ok": True, **data})
