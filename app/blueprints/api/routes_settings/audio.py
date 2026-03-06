from flask import jsonify, request
from . import api_settings_bp


@api_settings_bp.get("/audio/config")
def get_audio_config():
    """Récupère la configuration audio (STT/TTS)."""
    from ....services.audio_config_service import get_config
    return jsonify(get_config())


@api_settings_bp.post("/audio/config")
def set_audio_config():
    """Configure les paramètres audio."""
    from ....services.audio_config_service import set_config
    data = request.get_json(silent=True) or {}
    success = set_config(data)
    if not success:
        return jsonify({"error": "Échec de la sauvegarde"}), 500
    return jsonify({"ok": True})
