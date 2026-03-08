from flask import current_app

# Cache simple pour éviter de retester la connectivité à chaque requête
_ollama_url_cache: dict = {"url": None, "ts": 0}


def get_effective_ollama_base_url() -> str:
    """
    Get the effective Ollama base URL.

    Priority:
    1. Active provider if Ollama type (configured via UI)
    2. First reachable Ollama provider (configured via UI)
    3. OLLAMA_BASE_URL from config/env (fallback Docker)
    4. http://localhost:11434 (default)

    Results are cached for 60 seconds.
    """
    import time

    now = time.time()
    if _ollama_url_cache["url"] and (now - _ollama_url_cache["ts"]) < 60:
        return _ollama_url_cache["url"]

    url = _resolve_ollama_url()
    _ollama_url_cache["url"] = url
    _ollama_url_cache["ts"] = now
    return url


def _resolve_ollama_url() -> str:
    """Résout l'URL Ollama effective en testant la connectivité."""
    try:
        from app.services.provider_manager import get_provider_manager

        mgr = get_provider_manager()
        active_provider = mgr.get_active_provider(include_api_key=False)

        # 1. Si le provider actif est Ollama et joignable, l'utiliser
        if active_provider and active_provider.get("type") == "ollama":
            url = active_provider.get("url", "").rstrip("/")
            if url and _is_ollama_reachable(url):
                return url

        # 2. Tester tous les providers Ollama et retourner le premier joignable
        providers = mgr.get_providers(include_api_key_masked=False)
        for p in providers:
            if p.get("type") == "ollama" and p.get("url"):
                url = p["url"].rstrip("/")
                if _is_ollama_reachable(url):
                    return url

    except Exception as e:
        current_app.logger.warning(f"Failed to get Ollama URL from providers: {e}")

    # 3. Fallback env
    return current_app.config.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _is_ollama_reachable(url: str) -> bool:
    """Teste rapidement si un endpoint Ollama répond."""
    try:
        import httpx
        r = httpx.get(f"{url}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

