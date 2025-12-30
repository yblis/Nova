"""
RAG Configuration Service - Gestion des paramètres RAG persistants

Stocke les configurations RAG dans Redis pour persistance.
"""

from typing import Dict, Any, Optional
from flask import current_app
import json

REDIS_KEY = "rag:config"


def get_redis_client():
    """Get Redis client from Flask extensions."""
    from flask import g
    import redis
    
    if not hasattr(g, 'redis_client'):
        redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        g.redis_client = redis.from_url(redis_url)
    
    return g.redis_client


def get_rag_settings() -> Dict[str, Any]:
    """
    Récupère les paramètres RAG sauvegardés.
    
    Returns:
        Dict avec les paramètres (chunk_size, chunk_overlap, top_k, ocr_provider, etc.)
    """
    try:
        client = get_redis_client()
        data = client.get(REDIS_KEY)
        
        if data:
            return json.loads(data)
    except Exception as e:
        current_app.logger.warning(f"Could not read RAG config from Redis: {e}")
    
    # Retourner les valeurs par défaut
    return {
        "chunk_size": current_app.config.get("RAG_CHUNK_SIZE", 500),
        "chunk_overlap": current_app.config.get("RAG_CHUNK_OVERLAP", 50),
        "top_k": current_app.config.get("RAG_TOP_K", 5),
        "ocr_provider": current_app.config.get("RAG_OCR_PROVIDER", "auto"),
        "ocr_model": current_app.config.get("RAG_OCR_MODEL", ""),  # Modèle spécifique pour OCR
        "ocr_threshold": current_app.config.get("RAG_OCR_THRESHOLD", 50),
        "use_qdrant": current_app.config.get("RAG_USE_QDRANT", True)
    }


def save_rag_settings(settings: Dict[str, Any]) -> bool:
    """
    Sauvegarde les paramètres RAG.
    
    Args:
        settings: Dict avec les paramètres à sauvegarder
        
    Returns:
        True si succès
    """
    try:
        client = get_redis_client()
        
        # Merge with existing settings
        existing = get_rag_settings()
        existing.update(settings)
        
        client.set(REDIS_KEY, json.dumps(existing))
        current_app.logger.info(f"RAG config saved: {existing}")
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Could not save RAG config: {e}")
        return False


def get_setting(key: str, default: Any = None) -> Any:
    """
    Récupère un paramètre RAG spécifique.
    
    Args:
        key: Clé du paramètre
        default: Valeur par défaut
        
    Returns:
        Valeur du paramètre
    """
    settings = get_rag_settings()
    return settings.get(key, default)
