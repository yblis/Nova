from flask import current_app


def get_effective_ollama_base_url() -> str:
    """
    Get the effective Ollama base URL from the active provider.
    
    Uses the new ProviderManager to get the active provider's URL.
    Falls back to config OLLAMA_BASE_URL if no Ollama provider is configured.
    """
    try:
        from app.services.provider_manager import get_provider_manager
        
        mgr = get_provider_manager()
        active_provider = mgr.get_active_provider(include_api_key=False)
        
        if active_provider and active_provider.get("type") == "ollama":
            url = active_provider.get("url")
            if url:
                return url.rstrip("/")
        
        # If active provider is not Ollama, try to find any Ollama provider
        providers = mgr.get_providers(include_api_key_masked=False)
        for p in providers:
            if p.get("type") == "ollama" and p.get("url"):
                return p["url"].rstrip("/")
        
    except Exception as e:
        current_app.logger.warning(f"Failed to get Ollama URL from providers: {e}")
    
    # Fallback to config
    return current_app.config.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
