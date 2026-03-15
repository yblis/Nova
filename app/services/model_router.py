"""
Service de routage modèle → provider.

Cache la liste des modèles de chaque provider (locaux ET cloud)
et route automatiquement les requêtes vers le bon provider.
"""

from __future__ import annotations

import logging
import time
import threading
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .llm_clients.base_client import BaseLLMClient

logger = logging.getLogger(__name__)

LOCAL_PROVIDER_TYPES = {"ollama", "lmstudio", "openai_compatible"}

_model_provider_cache: Dict[str, dict] = {}
_cache_ts: float = 0
_cache_lock = threading.Lock()
_CACHE_TTL = 300  # 5 minutes (cloud API calls are slower)

_bg_refresh_running = False


def _index_local_provider(p: dict, new_cache: Dict[str, dict]) -> None:
    """Indexe les modèles d'un provider local via appels HTTP directs."""
    import httpx

    provider_id = p["id"]
    provider_type = p["type"]
    base_url = p["url"].rstrip("/")

    if provider_type == "ollama":
        r = httpx.get(f"{base_url}/api/tags", timeout=3)
        if r.status_code == 200:
            for m in r.json().get("models", []):
                model_name = m.get("name", "")
                if model_name:
                    new_cache[model_name] = {"id": provider_id, "type": provider_type}

    elif provider_type == "lmstudio":
        r = httpx.get(f"{base_url}/models", timeout=3)
        if r.status_code == 200:
            for m in r.json().get("data", []):
                model_id = m.get("id", "")
                if model_id:
                    new_cache[model_id] = {"id": provider_id, "type": provider_type}

    elif provider_type == "openai_compatible":
        endpoint = base_url
        if not endpoint.endswith("/v1"):
            endpoint = f"{endpoint}/v1"
        r = httpx.get(f"{endpoint}/models", timeout=3)
        if r.status_code == 200:
            for m in r.json().get("data", []):
                model_id = m.get("id", "")
                if model_id:
                    new_cache[model_id] = {"id": provider_id, "type": provider_type}


def _index_cloud_provider(p: dict, new_cache: Dict[str, dict]) -> None:
    """Indexe les modèles d'un provider cloud via son client LLM."""
    from .llm_clients import get_client_for_provider
    from .provider_manager import get_provider_manager

    provider_id = p["id"]
    provider_type = p["type"]

    mgr = get_provider_manager()
    provider_with_key = mgr.get_provider(provider_id, include_api_key=True)
    if not provider_with_key:
        return

    client = get_client_for_provider(provider_with_key)
    models = client.list_models()

    for m in models:
        if isinstance(m, dict):
            model_id = m.get("id") or m.get("name") or ""
        elif isinstance(m, str):
            model_id = m
        else:
            continue

        if model_id and model_id not in new_cache:
            new_cache[model_id] = {"id": provider_id, "type": provider_type}


def _refresh_cache() -> None:
    """Interroge tous les providers et mappe chaque modèle à son provider."""
    global _model_provider_cache, _cache_ts

    from .provider_manager import get_provider_manager

    mgr = get_provider_manager()
    providers = mgr.get_providers(include_api_key_masked=False)
    new_cache: Dict[str, dict] = {}

    for p in providers:
        provider_type = p.get("type", "")

        try:
            if provider_type in LOCAL_PROVIDER_TYPES:
                if p.get("url"):
                    _index_local_provider(p, new_cache)
            else:
                _index_cloud_provider(p, new_cache)
        except Exception as exc:
            logger.debug("model_router: skip provider %s (%s): %s", p.get("name"), provider_type, exc)
            continue

    _model_provider_cache = new_cache
    _cache_ts = time.time()
    logger.info("model_router: cache refreshed — %d models indexed across all providers", len(new_cache))


def _bg_refresh() -> None:
    """Rafraîchit le cache en arrière-plan sans bloquer les requêtes."""
    global _bg_refresh_running
    try:
        _refresh_cache()
    finally:
        _bg_refresh_running = False


def _ensure_cache() -> Dict[str, dict]:
    """Retourne le cache, le rafraîchit si expiré.

    Le premier appel fait un refresh synchrone (local uniquement pour la rapidité).
    Les refreshs suivants se font en arrière-plan pour ne pas bloquer.
    """
    global _cache_ts, _bg_refresh_running
    now = time.time()
    if (now - _cache_ts) > _CACHE_TTL:
        with _cache_lock:
            if (time.time() - _cache_ts) > _CACHE_TTL:
                if _cache_ts == 0:
                    _refresh_cache()
                elif not _bg_refresh_running:
                    _bg_refresh_running = True
                    t = threading.Thread(target=_bg_refresh, daemon=True)
                    t.start()
    return _model_provider_cache


def invalidate_cache() -> None:
    """Force la réinitialisation du cache au prochain appel."""
    global _cache_ts
    _cache_ts = 0


def resolve_provider_for_model(model: str) -> Optional[dict]:
    """Résout le provider approprié pour un modèle donné.

    Returns:
        Le provider dict (avec api_key) si trouvé, None sinon.
    """
    if not model:
        return None

    cache = _ensure_cache()
    provider_ref = cache.get(model)
    if not provider_ref:
        return None

    from .provider_manager import get_provider_manager
    mgr = get_provider_manager()
    return mgr.get_provider(provider_ref["id"], include_api_key=True)


def get_client_for_model(model: str = None) -> "BaseLLMClient":
    """Retourne le client LLM approprié pour un modèle donné.

    1. Si le modèle est trouvé dans le cache → utilise le provider correspondant
    2. Sinon → utilise le provider actif
    3. Fallback → OllamaClient direct
    """
    from .llm_clients import get_active_client, get_client_for_provider
    from .llm_error_handler import LLMError

    if model:
        provider = resolve_provider_for_model(model)
        if provider:
            return get_client_for_provider(provider)

    try:
        client = get_active_client()
        if client:
            return client
    except (LLMError, ValueError):
        pass

    from flask import current_app
    from .ollama_client import OllamaClient
    from ..utils import get_effective_ollama_base_url
    return OllamaClient(
        base_url=get_effective_ollama_base_url(),
        connect_timeout=current_app.config.get("HTTP_CONNECT_TIMEOUT", 10),
        read_timeout=current_app.config.get("HTTP_READ_TIMEOUT", 120),
    )
