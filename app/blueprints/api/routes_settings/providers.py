from flask import jsonify, request, current_app
from . import api_settings_bp, _get_provider_manager, _validate_base_url


@api_settings_bp.get("/provider-types")
def get_provider_types():
    """Retourne les types de fournisseurs disponibles avec leurs métadonnées."""
    from ....services.provider_manager import get_provider_types
    types = get_provider_types()
    return jsonify({"types": types})


@api_settings_bp.get("/providers")
def get_providers():
    """Liste tous les fournisseurs configurés."""
    mgr = _get_provider_manager()
    providers = mgr.get_providers()

    exclude_audio = request.args.get("exclude_audio", "false").lower() == "true"
    if exclude_audio:
        providers = [
            p for p in providers
            if "(TTS)" not in p.get("name", "") and "(STT)" not in p.get("name", "")
        ]

    return jsonify({
        "providers": providers,
        "active_provider_id": mgr.get_active_provider_id()
    })


@api_settings_bp.post("/providers")
def add_provider():
    """Ajoute un nouveau fournisseur LLM."""
    from ....services.provider_manager import PROVIDER_TYPES

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    provider_type = (data.get("type") or "").strip()
    url = (data.get("url") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    extra_headers = data.get("extra_headers", {})

    if not name:
        return jsonify({"error": "Le nom est requis"}), 400
    if provider_type not in PROVIDER_TYPES:
        return jsonify({"error": f"Type de fournisseur invalide: {provider_type}"}), 400

    type_config = PROVIDER_TYPES[provider_type]
    if type_config.get("requires_url") and url:
        ok, err = _validate_base_url(url)
        if not ok:
            return jsonify({"error": err}), 400
    if type_config.get("requires_api_key") and not api_key:
        return jsonify({"error": "La clé API est requise pour ce fournisseur"}), 400

    try:
        mgr = _get_provider_manager()
        provider = mgr.add_provider(name=name, provider_type=provider_type, url=url, api_key=api_key, extra_headers=extra_headers)
        from ....services.model_router import invalidate_cache
        invalidate_cache()
        return jsonify(provider)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error adding provider: {e}")
        return jsonify({"error": "Erreur lors de l'ajout du fournisseur"}), 500


@api_settings_bp.put("/providers/<provider_id>")
def update_provider(provider_id):
    """Met à jour un fournisseur existant."""
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    url = data.get("url")
    api_key = data.get("api_key")
    extra_headers = data.get("extra_headers")

    if url is not None and url.strip():
        ok, err = _validate_base_url(url.strip())
        if not ok:
            return jsonify({"error": err}), 400

    try:
        mgr = _get_provider_manager()
        provider = mgr.update_provider(
            provider_id=provider_id,
            name=name.strip() if name else None,
            url=url.strip() if url else None,
            api_key=api_key if api_key else None,
            extra_headers=extra_headers
        )
        if not provider:
            return jsonify({"error": "Fournisseur non trouvé"}), 404
        from ....services.model_router import invalidate_cache
        invalidate_cache()
        return jsonify(provider)
    except Exception as e:
        current_app.logger.error(f"Error updating provider: {e}")
        return jsonify({"error": "Erreur lors de la mise à jour"}), 500


@api_settings_bp.delete("/providers/<provider_id>")
def delete_provider(provider_id):
    """Supprime un fournisseur."""
    mgr = _get_provider_manager()
    success = mgr.delete_provider(provider_id)
    if not success:
        return jsonify({"error": "Fournisseur non trouvé"}), 404
    from ....services.model_router import invalidate_cache
    invalidate_cache()
    return jsonify({"ok": True})


@api_settings_bp.post("/providers/active")
def set_active_provider():
    """Définit le fournisseur actif."""
    data = request.get_json(silent=True) or {}
    provider_id = data.get("provider_id")
    if not provider_id:
        return jsonify({"error": "provider_id requis"}), 400
    mgr = _get_provider_manager()
    if mgr.set_active_provider(provider_id):
        from ....services.model_router import invalidate_cache
        invalidate_cache()
        return jsonify({"ok": True})
    return jsonify({"error": "Fournisseur non trouvé"}), 404


@api_settings_bp.post("/providers/<provider_id>/test")
def test_provider(provider_id):
    """Teste la connexion à un fournisseur."""
    from ....services.llm_clients import get_client_for_provider
    mgr = _get_provider_manager()
    provider = mgr.get_provider(provider_id, include_api_key=True)
    if not provider:
        return jsonify({"error": "Fournisseur non trouvé"}), 404
    try:
        client = get_client_for_provider(provider)
        success, message = client.test_connection()
        return jsonify({"ok": success, "message": message})
    except Exception as e:
        return jsonify({"ok": False, "message": f"Erreur: {str(e)}"})


@api_settings_bp.get("/providers/<provider_id>/models")
def get_provider_models(provider_id):
    """Liste les modèles disponibles pour un fournisseur."""
    from ....services.llm_clients import get_client_for_provider
    from ....services.llm_error_handler import LLMError

    mgr = _get_provider_manager()
    provider = mgr.get_provider(provider_id, include_api_key=True)
    if not provider:
        return jsonify({"error": "Fournisseur non trouvé"}), 404

    try:
        client = get_client_for_provider(provider)
        models = client.list_models()
        return jsonify({
            "models": models,
            "default_model": client.get_default_model(),
            "provider_default_model": provider.get("default_model", "")
        })
    except LLMError as e:
        return jsonify({"error": e.get_user_message(), "models": []}), 400
    except Exception as e:
        current_app.logger.error(f"Error listing models: {e}")
        return jsonify({"error": f"Erreur: {str(e)}", "models": []}), 500


@api_settings_bp.get("/providers/active/models")
def get_active_provider_models():
    """Liste les modèles du fournisseur actif."""
    from ....services.llm_clients import get_client_for_provider
    from ....services.llm_error_handler import LLMError

    mgr = _get_provider_manager()
    provider = mgr.get_active_provider()
    if not provider:
        return jsonify({"error": "Aucun fournisseur actif", "models": []}), 400

    try:
        provider_with_key = mgr.get_active_provider(include_api_key=True)
        client = get_client_for_provider(provider_with_key)
        models = client.list_models()
        return jsonify({
            "models": models,
            "default_model": client.get_default_model(),
            "provider_default_model": provider.get("default_model", ""),
            "provider": {"id": provider["id"], "name": provider["name"], "type": provider["type"]}
        })
    except LLMError as e:
        return jsonify({"error": e.get_user_message(), "models": []}), 400
    except Exception as e:
        return jsonify({"error": f"Erreur: {str(e)}", "models": []}), 500


@api_settings_bp.post("/providers/migrate")
def migrate_providers():
    """Migre les serveurs Ollama existants vers le nouveau format providers."""
    from ....services.provider_manager import migrate_from_servers
    try:
        migrated = migrate_from_servers()
        if migrated:
            return jsonify({"ok": True, "message": "Migration effectuée"})
        return jsonify({"ok": True, "message": "Aucune migration nécessaire"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_settings_bp.post("/providers/<provider_id>/default-model")
def set_provider_default_model(provider_id):
    """Définit le modèle par défaut pour un fournisseur."""
    data = request.get_json(silent=True) or {}
    model_name = data.get("model", "")
    mgr = _get_provider_manager()
    provider = mgr.get_provider(provider_id)
    if not provider:
        return jsonify({"error": "Fournisseur non trouvé"}), 404
    success = mgr.set_default_model(provider_id, model_name)
    if success:
        return jsonify({"ok": True, "default_model": model_name})
    return jsonify({"error": "Échec de la mise à jour"}), 500


@api_settings_bp.post("/providers/resolve-model")
def resolve_model_provider():
    """Trouve le provider qui contient un modèle donné."""
    from ....services.llm_clients import get_client_for_provider

    data = request.get_json(silent=True) or {}
    model_name = (data.get("model") or "").strip()
    if not model_name:
        return jsonify({"error": "model requis", "found": False}), 400

    mgr = _get_provider_manager()
    providers = mgr.get_providers()

    for provider in providers:
        try:
            provider_with_key = mgr.get_provider(provider["id"], include_api_key=True)
            if not provider_with_key:
                continue
            client = get_client_for_provider(provider_with_key)
            models = client.list_models()
            model_names = []
            for m in models:
                if isinstance(m, str):
                    model_names.append(m)
                elif isinstance(m, dict):
                    model_names.append(m.get("id") or m.get("name") or "")
            if model_name in model_names:
                return jsonify({
                    "found": True,
                    "provider_id": provider["id"],
                    "provider_type": provider["type"],
                    "provider_name": provider["name"]
                })
        except Exception as e:
            current_app.logger.debug(f"Could not check models for provider {provider['id']}: {e}")
            continue

    return jsonify({"found": False, "message": f"Modèle '{model_name}' non trouvé dans les providers configurés"})
