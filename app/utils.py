from flask import current_app


def get_effective_ollama_base_url() -> str:
    """
    Get the effective Ollama base URL.

    Priority:
    1. OLLAMA_BASE_URL from config/env (always correct in Docker)
    2. Active provider URL if it's an Ollama provider
    3. Any configured Ollama provider URL
    4. http://localhost:11434 (default)
    """
    # 1. Config/env variable has highest priority (set by docker-compose)
    config_url = current_app.config.get("OLLAMA_BASE_URL", "").strip()
    if config_url:
        return config_url.rstrip("/")

    # 2. Try ProviderManager
    try:
        from app.services.provider_manager import get_provider_manager

        mgr = get_provider_manager()
        active_provider = mgr.get_active_provider(include_api_key=False)

        if active_provider and active_provider.get("type") == "ollama":
            url = active_provider.get("url")
            if url:
                return url.rstrip("/")

        # 3. Any Ollama provider
        providers = mgr.get_providers(include_api_key_masked=False)
        for p in providers:
            if p.get("type") == "ollama" and p.get("url"):
                return p["url"].rstrip("/")

    except Exception as e:
        current_app.logger.warning(f"Failed to get Ollama URL from providers: {e}")

    # 4. Default fallback
    return "http://localhost:11434"

