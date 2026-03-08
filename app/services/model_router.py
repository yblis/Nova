"""
Service de routage modèle → provider.

Cache la liste des modèles de chaque provider local (Ollama, LM Studio)
et route automatiquement les requêtes vers le bon provider.
"""

from __future__ import annotations

import time
import threading
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .llm_clients.base_client import BaseLLMClient


# Types de providers "locaux" (pas les API cloud)
LOCAL_PROVIDER_TYPES = {"ollama", "lmstudio"}

# Cache global: modèle → provider dict
_model_provider_cache: Dict[str, dict] = {}
_cache_ts: float = 0
_cache_lock = threading.Lock()
_CACHE_TTL = 120  # 2 minutes


def _refresh_cache() -> None:
    """Interroge tous les providers locaux et mappe chaque modèle à son provider."""
    global _model_provider_cache, _cache_ts

    from .provider_manager import get_provider_manager

    mgr = get_provider_manager()
    providers = mgr.get_providers(include_api_key_masked=False)
    new_cache: Dict[str, dict] = {}

    for p in providers:
        if p.get("type") not in LOCAL_PROVIDER_TYPES:
            continue
        if not p.get("url"):
            continue

        provider_id = p["id"]
        provider_type = p["type"]
        base_url = p["url"].rstrip("/")

        try:
            if provider_type == "ollama":
                import httpx
                r = httpx.get(f"{base_url}/api/tags", timeout=3)
                if r.status_code == 200:
                    for m in r.json().get("models", []):
                        model_name = m.get("name", "")
                        if model_name:
                            new_cache[model_name] = {"id": provider_id, "type": provider_type}

            elif provider_type == "lmstudio":
                import httpx
                r = httpx.get(f"{base_url}/models", timeout=3)
                if r.status_code == 200:
                    for m in r.json().get("data", []):
                        model_id = m.get("id", "")
                        if model_id:
                            new_cache[model_id] = {"id": provider_id, "type": provider_type}
        except Exception:
            continue  # Provider inaccessible, on skip

    _model_provider_cache = new_cache
    _cache_ts = time.time()


def _ensure_cache() -> Dict[str, dict]:
    """Retourne le cache, le rafraîchit si expiré."""
    global _cache_ts
    now = time.time()
    if (now - _cache_ts) > _CACHE_TTL:
        with _cache_lock:
            if (time.time() - _cache_ts) > _CACHE_TTL:  # double-check
                _refresh_cache()
    return _model_provider_cache


def resolve_provider_for_model(model: str) -> Optional[dict]:
    """Résout le provider approprié pour un modèle donné.
    
    Returns:
        Le provider dict (avec api_key) si le modèle est trouvé sur un provider local,
        None si le modèle n'est pas trouvé (utiliser le provider actif par défaut).
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
    
    1. Si le modèle est trouvé sur un provider local → utilise ce provider
    2. Sinon → utilise le provider actif (API cloud)
    3. Fallback → OllamaClient direct
    """
    from .llm_clients import get_active_client, get_client_for_provider
    from .llm_error_handler import LLMError

    # 1. Résoudre via le cache modèle→provider
    if model:
        provider = resolve_provider_for_model(model)
        if provider:
            return get_client_for_provider(provider)

    # 2. Provider actif (API cloud)
    try:
        client = get_active_client()
        if client:
            return client
    except (LLMError, ValueError):
        pass

    # 3. Fallback OllamaClient
    from flask import current_app
    from .ollama_client import OllamaClient
    from ..utils import get_effective_ollama_base_url
    return OllamaClient(
        base_url=get_effective_ollama_base_url(),
        connect_timeout=current_app.config.get("HTTP_CONNECT_TIMEOUT", 10),
        read_timeout=current_app.config.get("HTTP_READ_TIMEOUT", 120),
    )
