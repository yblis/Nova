from flask import jsonify, request
from . import api_settings_bp, _validate_base_url


@api_settings_bp.get("/bookstack/config")
def get_bookstack_config():
    """Récupère la configuration Bookstack."""
    from ....services.bookstack_service import get_config, is_bookstack_available
    config = get_config()
    return jsonify({
        "url": config.get("url", ""),
        "token_id": config.get("token_id", ""),
        "token_secret_masked": config.get("token_secret_masked", ""),
        "max_results": config.get("max_results", 5),
        "timeout": config.get("timeout", 15),
        "is_available": is_bookstack_available()
    })


@api_settings_bp.post("/bookstack/config")
def set_bookstack_config():
    """Configure les paramètres Bookstack."""
    from ....services.bookstack_service import set_config
    data = request.get_json(silent=True) or {}
    updates = {}

    if "url" in data:
        url = (data.get("url") or "").strip()
        if url:
            ok, err = _validate_base_url(url)
            if not ok:
                return jsonify({"error": err}), 400
        updates["url"] = url

    if "token_id" in data:
        updates["token_id"] = (data.get("token_id") or "").strip()
    if "token_secret" in data:
        updates["token_secret"] = (data.get("token_secret") or "").strip()

    if "max_results" in data:
        try:
            max_results = int(data["max_results"])
            if 1 <= max_results <= 20:
                updates["max_results"] = max_results
            else:
                return jsonify({"error": "max_results doit être entre 1 et 20"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "max_results invalide"}), 400

    if "timeout" in data:
        try:
            timeout = int(data["timeout"])
            if 1 <= timeout <= 60:
                updates["timeout"] = timeout
            else:
                return jsonify({"error": "timeout doit être entre 1 et 60 secondes"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "timeout invalide"}), 400

    if updates:
        success = set_config(updates)
        if not success:
            return jsonify({"error": "Échec de la sauvegarde"}), 500

    return jsonify({"ok": True})


@api_settings_bp.post("/bookstack/test")
def test_bookstack():
    """Teste la connexion au serveur Bookstack."""
    from ....services.bookstack_service import test_connection
    result = test_connection()
    status_code = 200 if result.get("ok") else 500
    return jsonify(result), status_code
