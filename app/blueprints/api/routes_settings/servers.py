from flask import jsonify, request
from . import api_settings_bp, _get_manager, _validate_base_url


@api_settings_bp.get("/servers")
def get_servers():
    mgr = _get_manager()
    return jsonify({
        "servers": mgr.get_servers(),
        "active_server_id": mgr._load_data().get("active_server_id")
    })


@api_settings_bp.post("/servers")
def add_server():
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "New Server").strip()
    url = (data.get("url") or "").strip()
    ok, err = _validate_base_url(url)
    if not ok:
        return jsonify({"error": err}), 400
    mgr = _get_manager()
    server = mgr.add_server(name, url)
    return jsonify(server)


@api_settings_bp.put("/servers/<server_id>")
def update_server(server_id):
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "Updated Server").strip()
    url = (data.get("url") or "").strip()
    ok, err = _validate_base_url(url)
    if not ok:
        return jsonify({"error": err}), 400
    mgr = _get_manager()
    server = mgr.update_server(server_id, name, url)
    if not server:
        return jsonify({"error": "Server not found"}), 404
    return jsonify(server)


@api_settings_bp.delete("/servers/<server_id>")
def delete_server(server_id):
    mgr = _get_manager()
    success = mgr.delete_server(server_id)
    if not success:
        return jsonify({"error": "Server not found/could not delete"}), 404
    return jsonify({"ok": True})


@api_settings_bp.post("/servers/active")
def set_active_server():
    data = request.get_json(silent=True) or {}
    server_id = data.get("server_id")
    if not server_id:
        return jsonify({"error": "Missing server_id"}), 400
    mgr = _get_manager()
    if mgr.set_active_server(server_id):
        return jsonify({"ok": True})
    return jsonify({"error": "Server not found"}), 404


@api_settings_bp.get("/ollama_base_url")
def get_ollama_base_url():
    mgr = _get_manager()
    return jsonify({"ollama_base_url": mgr.get_active_server_url()})
