from flask import Blueprint, jsonify, request, current_app
from app.services.server_manager import ServerManager

api_settings_bp = Blueprint("api_settings", __name__)


def _get_manager() -> ServerManager:
    # We'll attach the manager to app context or init it here
    # For simplicity, init with default path
    data_path = current_app.root_path + "/data/servers.json"
    return ServerManager(data_path)

def _validate_base_url(url: str) -> tuple[bool, str | None]:
    url = (url or "").strip()
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
    except Exception:
        return False, "URL invalide"
    if p.scheme not in {"http", "https"}:
        return False, "Schéma doit être http ou https"
    if not p.netloc:
        return False, "Hôte requis"
    return True, None


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

# Keep legacy endpoint for compatibility if needed, but point to active
@api_settings_bp.get("/ollama_base_url")
def get_ollama_base_url():
    mgr = _get_manager()
    return jsonify({"ollama_base_url": mgr.get_active_server_url()})


# ============== Web Search (SearXNG) Configuration ==============

@api_settings_bp.get("/web_search/config")
def get_web_search_config():
    """Récupère la configuration de recherche web SearXNG."""
    from ...services.web_search_service import get_config, is_searxng_available
    
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
    from ...services.web_search_service import set_config
    
    data = request.get_json(silent=True) or {}
    
    updates = {}
    
    # Valider et mettre à jour l'URL si fournie
    if "searxng_url" in data:
        url = (data.get("searxng_url") or "").strip()
        if url:
            ok, err = _validate_base_url(url)
            if not ok:
                return jsonify({"error": err}), 400
        updates["searxng_url"] = url
    
    # Mettre à jour max_results si fourni
    if "max_results" in data:
        try:
            max_results = int(data["max_results"])
            if 1 <= max_results <= 20:
                updates["max_results"] = max_results
            else:
                return jsonify({"error": "max_results doit être entre 1 et 20"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "max_results invalide"}), 400
    
    # Mettre à jour timeout si fourni
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
    from ...services.web_search_service import search_web, get_searxng_url
    
    url = get_searxng_url()
    if not url:
        return jsonify({"error": "URL SearXNG non configurée"}), 400
    
    try:
        results = search_web("test", max_results=1)
        return jsonify({
            "ok": True,
            "message": f"Connexion réussie ! {len(results)} résultat(s) obtenu(s).",
            "results_count": len(results)
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Échec de connexion : {str(e)}"
        }), 500


# ============== LLM Configuration ==============

@api_settings_bp.get("/llm/config")
def get_llm_config():
    """Récupère la configuration LLM par défaut."""
    from ...services.llm_config_service import get_config
    
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
    from ...services.llm_config_service import set_config
    
    data = request.get_json(silent=True) or {}
    
    # Valider les paramètres numériques
    if "temperature" in data:
        try:
            temp = float(data["temperature"])
            if not (0 <= temp <= 2):
                return jsonify({"error": "temperature doit être entre 0 et 2"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "temperature invalide"}), 400
    
    if "top_p" in data:
        try:
            top_p = float(data["top_p"])
            if not (0 <= top_p <= 1):
                return jsonify({"error": "top_p doit être entre 0 et 1"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "top_p invalide"}), 400
    
    if "top_k" in data:
        try:
            top_k = int(data["top_k"])
            if not (1 <= top_k <= 100):
                return jsonify({"error": "top_k doit être entre 1 et 100"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "top_k invalide"}), 400
    
    if "repeat_penalty" in data:
        try:
            rp = float(data["repeat_penalty"])
            if not (1 <= rp <= 2):
                return jsonify({"error": "repeat_penalty doit être entre 1 et 2"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "repeat_penalty invalide"}), 400
    
    if "num_ctx" in data:
        try:
            num_ctx = int(data["num_ctx"])
            if not (2048 <= num_ctx <= 128000):
                return jsonify({"error": "num_ctx doit être entre 2048 et 128000"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "num_ctx invalide"}), 400
    
    success = set_config(data)
    if not success:
        return jsonify({"error": "Échec de la sauvegarde"}), 500
    
    return jsonify({"ok": True, **data})


    return jsonify({"ok": True, **data})


# ============== Audio Configuration ==============

@api_settings_bp.get("/audio/config")
def get_audio_config():
    """Récupère la configuration audio (STT/TTS)."""
    from ...services.audio_config_service import get_config
    
    return jsonify(get_config())


@api_settings_bp.post("/audio/config")
def set_audio_config():
    """Configure les paramètres audio."""
    from ...services.audio_config_service import set_config
    
    data = request.get_json(silent=True) or {}
    success = set_config(data)
    
    if not success:
        return jsonify({"error": "Échec de la sauvegarde"}), 500
    
    return jsonify({"ok": True})


# ============== LLM Providers Management ==============

def _get_provider_manager():
    """Retourne une instance du ProviderManager."""
    from ...services.provider_manager import ProviderManager
    data_path = current_app.root_path + "/data/providers.json"
    return ProviderManager(data_path)


@api_settings_bp.get("/provider-types")
def get_provider_types():
    """Retourne les types de fournisseurs disponibles avec leurs métadonnées."""
    from ...services.provider_manager import get_provider_types
    
    types = get_provider_types()
    return jsonify({"types": types})


@api_settings_bp.get("/providers")
def get_providers():
    """Liste tous les fournisseurs configurés."""
    mgr = _get_provider_manager()
    providers = mgr.get_providers()
    
    # Filtrer les providers audio (TTS/STT) si demandé
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
    from ...services.provider_manager import PROVIDER_TYPES
    
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
    
    # Valider l'URL si requise
    if type_config.get("requires_url") and url:
        ok, err = _validate_base_url(url)
        if not ok:
            return jsonify({"error": err}), 400
    
    # Valider la clé API si requise
    if type_config.get("requires_api_key") and not api_key:
        return jsonify({"error": "La clé API est requise pour ce fournisseur"}), 400
    
    try:
        mgr = _get_provider_manager()
        provider = mgr.add_provider(
            name=name,
            provider_type=provider_type,
            url=url,
            api_key=api_key,
            extra_headers=extra_headers
        )
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
    
    # Valider l'URL si fournie
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
        return jsonify({"ok": True})
    
    return jsonify({"error": "Fournisseur non trouvé"}), 404


@api_settings_bp.post("/providers/<provider_id>/test")
def test_provider(provider_id):
    """Teste la connexion à un fournisseur."""
    from ...services.llm_clients import get_client_for_provider
    
    mgr = _get_provider_manager()
    provider = mgr.get_provider(provider_id, include_api_key=True)
    
    if not provider:
        return jsonify({"error": "Fournisseur non trouvé"}), 404
    
    try:
        client = get_client_for_provider(provider)
        success, message = client.test_connection()
        
        return jsonify({
            "ok": success,
            "message": message
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "message": f"Erreur: {str(e)}"
        })


@api_settings_bp.get("/providers/<provider_id>/models")
def get_provider_models(provider_id):
    """Liste les modèles disponibles pour un fournisseur."""
    from ...services.llm_clients import get_client_for_provider
    from ...services.llm_error_handler import LLMError
    
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
        return jsonify({
            "error": e.get_user_message(),
            "models": []
        }), 400
    except Exception as e:
        current_app.logger.error(f"Error listing models: {e}")
        return jsonify({
            "error": f"Erreur: {str(e)}",
            "models": []
        }), 500


@api_settings_bp.get("/providers/active/models")
def get_active_provider_models():
    """Liste les modèles du fournisseur actif."""
    from ...services.llm_clients import get_active_client
    from ...services.llm_error_handler import LLMError
    
    mgr = _get_provider_manager()
    provider = mgr.get_active_provider()
    
    if not provider:
        return jsonify({"error": "Aucun fournisseur actif", "models": []}), 400
    
    try:
        provider_with_key = mgr.get_active_provider(include_api_key=True)
        from ...services.llm_clients import get_client_for_provider
        client = get_client_for_provider(provider_with_key)
        models = client.list_models()
        
        return jsonify({
            "models": models,
            "default_model": client.get_default_model(),
            "provider_default_model": provider.get("default_model", ""),
            "provider": {
                "id": provider["id"],
                "name": provider["name"],
                "type": provider["type"]
            }
        })
    except LLMError as e:
        return jsonify({
            "error": e.get_user_message(),
            "models": []
        }), 400
    except Exception as e:
        return jsonify({
            "error": f"Erreur: {str(e)}",
            "models": []
        }), 500


@api_settings_bp.post("/providers/migrate")
def migrate_providers():
    """Migre les serveurs Ollama existants vers le nouveau format providers."""
    from ...services.provider_manager import migrate_from_servers
    
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
    
    # Vérifier que le provider existe
    provider = mgr.get_provider(provider_id)
    if not provider:
        return jsonify({"error": "Fournisseur non trouvé"}), 404
    
    success = mgr.set_default_model(provider_id, model_name)
    if success:
        return jsonify({"ok": True, "default_model": model_name})
    
    return jsonify({"error": "Échec de la mise à jour"}), 500


@api_settings_bp.post("/providers/resolve-model")
def resolve_model_provider():
    """
    Trouve le provider qui contient un modèle donné.
    Parcourt tous les providers configurés et retourne le premier qui contient ce modèle.
    """
    from ...services.llm_clients import get_client_for_provider
    
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
            
            # Normaliser les noms de modèles pour la comparaison
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
            # En cas d'erreur sur un provider, passer au suivant
            current_app.logger.debug(f"Could not check models for provider {provider['id']}: {e}")
            continue
    
    # Modèle non trouvé dans aucun provider
    return jsonify({
        "found": False,
        "message": f"Modèle '{model_name}' non trouvé dans les providers configurés"
    })


