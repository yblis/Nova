from flask import jsonify, request
from . import api_settings_bp, _validate_base_url


@api_settings_bp.get("/web_search/config")
def get_web_search_config():
    """Récupère la configuration de recherche web SearXNG."""
    from ....services.web_search_service import get_config, is_searxng_available
    config = get_config()
    return jsonify({
        "searxng_url": config.get("searxng_url", ""),
        "max_results": config.get("max_results", 5),
        "timeout": config.get("timeout", 10),
        "is_available": is_searxng_available()
    })


@api_settings_bp.post("/web_search/config")
def set_web_search_config():
    """Configure les paramètres de recherche web SearXNG."""
    from ....services.web_search_service import set_config
    data = request.get_json(silent=True) or {}
    updates = {}

    if "searxng_url" in data:
        url = (data.get("searxng_url") or "").strip()
        if url:
            ok, err = _validate_base_url(url)
            if not ok:
                return jsonify({"error": err}), 400
        updates["searxng_url"] = url

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

    return jsonify({"ok": True, **updates})


@api_settings_bp.post("/web_search/test")
def test_web_search():
    """Teste la connexion au serveur SearXNG."""
    from ....services.web_search_service import search_web, get_searxng_url
    url = get_searxng_url()
    if not url:
        return jsonify({"error": "URL SearXNG non configurée"}), 400
    try:
        results = search_web("test", max_results=1)
        return jsonify({"ok": True, "message": f"Connexion réussie ! {len(results)} résultat(s) obtenu(s).", "results_count": len(results)})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Échec de connexion : {str(e)}"}), 500
