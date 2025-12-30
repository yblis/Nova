"""
Package des clients LLM.

Ce package contient les implémentations de clients pour différents fournisseurs LLM.
Une factory permet d'obtenir le client approprié selon le type de fournisseur.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base_client import BaseLLMClient


def get_client_for_provider(provider: dict) -> "BaseLLMClient":
    """
    Factory pour obtenir le client LLM approprié.
    
    Args:
        provider: Dictionnaire contenant les infos du provider
                  (type, url, api_key, extra_headers)
    
    Returns:
        Instance du client LLM approprié
        
    Raises:
        ValueError: Si le type de provider n'est pas supporté
    """
    provider_type = provider.get("type", "")
    
    if provider_type == "ollama":
        from .ollama_adapter import OllamaAdapter
        return OllamaAdapter(
            base_url=provider.get("url", "http://localhost:11434")
        )
    
    elif provider_type in ("openai", "lmstudio", "groq", "mistral", "openrouter", "deepseek", "openai_compatible"):
        from .openai_compatible_client import OpenAICompatibleClient
        return OpenAICompatibleClient(
            provider_type=provider_type,
            base_url=provider.get("url"),
            api_key=provider.get("api_key", ""),
            extra_headers=provider.get("extra_headers", {})
        )
    
    elif provider_type == "anthropic":
        from .anthropic_client import AnthropicClient
        return AnthropicClient(
            api_key=provider.get("api_key", "")
        )
    
    elif provider_type == "gemini":
        from .gemini_client import GeminiClient
        return GeminiClient(
            api_key=provider.get("api_key", "")
        )
    
    elif provider_type == "qwen":
        from .qwen_client import QwenClient
        return QwenClient(
            api_key=provider.get("api_key", "")
        )
    
    else:
        raise ValueError(f"Type de fournisseur non supporté: {provider_type}")


def get_active_client() -> "BaseLLMClient":
    """
    Retourne le client pour le fournisseur actif.
    
    Returns:
        Client LLM pour le provider actif
        
    Raises:
        ValueError: Si aucun provider n'est configuré
    """
    from ..provider_manager import get_provider_manager
    
    mgr = get_provider_manager()
    provider = mgr.get_active_provider(include_api_key=True)
    
    if not provider:
        raise ValueError("Aucun fournisseur LLM configuré")
    
    return get_client_for_provider(provider)


__all__ = [
    "get_client_for_provider",
    "get_active_client",
    "BaseLLMClient"
]
