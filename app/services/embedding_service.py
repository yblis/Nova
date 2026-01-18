"""
Embedding Service - Génération d'embeddings multi-provider

Supporte: Ollama, OpenAI, Cohere, et tout provider configuré.
"""

import httpx
from typing import List, Optional, Dict, Any
from flask import current_app


def get_redis_client():
    """Get Redis client from Flask app or create new one."""
    # Try current_app.redis first (initialized in extensions.py)
    try:
        if current_app.redis:
            return current_app.redis
    except Exception:
        pass
    
    # Fallback: create new redis connection
    try:
        import redis
        redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
        return redis.from_url(redis_url)
    except Exception as e:
        current_app.logger.error(f"Could not connect to Redis: {e}")
        return None


def get_embedding_provider_id() -> Optional[str]:
    """
    Récupère l'ID du provider d'embedding configuré depuis Redis.
    
    Returns:
        ID du provider ou None si non configuré (utilise Ollama par défaut)
    """
    try:
        client = get_redis_client()
        if client:
            provider_id = client.get("rag:embedding_provider_id")
            if provider_id:
                return provider_id.decode('utf-8') if isinstance(provider_id, bytes) else provider_id
    except Exception as e:
        current_app.logger.warning(f"Error getting embedding provider: {e}")
    return None


def set_embedding_provider_id(provider_id: str) -> bool:
    """
    Configure le provider d'embedding dans Redis.
    
    Args:
        provider_id: ID du provider à utiliser
        
    Returns:
        True si succès
    """
    try:
        client = get_redis_client()
        if client:
            client.set("rag:embedding_provider_id", provider_id)
            current_app.logger.info(f"Embedding provider set to: {provider_id}")
            return True
        else:
            current_app.logger.error("No Redis client available to save embedding provider")
    except Exception as e:
        current_app.logger.error(f"Error setting embedding provider: {e}")
    return False


def get_embedding_model() -> Optional[str]:
    """
    Récupère le modèle d'embedding configuré depuis Redis.
    
    Returns:
        Nom du modèle ou None si non configuré
    """
    try:
        client = get_redis_client()
        if client:
            model = client.get("rag:embedding_model")
            if model:
                return model.decode('utf-8') if isinstance(model, bytes) else model
    except Exception as e:
        current_app.logger.warning(f"Error getting embedding model: {e}")
    return None


def set_embedding_model(model_name: str) -> bool:
    """
    Configure le modèle d'embedding dans Redis.
    
    Args:
        model_name: Nom du modèle à utiliser
        
    Returns:
        True si succès
    """
    try:
        client = get_redis_client()
        if client:
            client.set("rag:embedding_model", model_name)
            current_app.logger.info(f"Embedding model set to: {model_name}")
            return True
        else:
            current_app.logger.error("No Redis client available to save embedding model")
    except Exception as e:
        current_app.logger.error(f"Error setting embedding model: {e}")
    return False


def get_embedding_dimensions(model_name: str) -> int:
    """
    Retourne le nombre de dimensions pour un modèle d'embedding connu.
    Si inconnu, retourne 768 par défaut.
    """
    known_dimensions = {
        # Ollama models
        'nomic-embed-text': 768,
        'all-minilm': 384,
        'mxbai-embed-large': 1024,
        'snowflake-arctic-embed': 1024,
        'bge-m3': 1024,
        'bge-large': 1024,
        # OpenAI models
        'text-embedding-3-small': 1536,
        'text-embedding-3-large': 3072,
        'text-embedding-ada-002': 1536,
        # Cohere models
        'embed-english-v3.0': 1024,
        'embed-multilingual-v3.0': 1024,
        'embed-english-light-v3.0': 384,
        'embed-multilingual-light-v3.0': 384,
    }
    
    # Chercher correspondance partielle
    model_lower = model_name.lower()
    for key, dim in known_dimensions.items():
        if key in model_lower:
            return dim
    
    return 768  # Défaut


def _generate_embedding_ollama(text: str, model: str, base_url: str) -> Optional[List[float]]:
    """Génère un embedding via Ollama."""
    url = f"{base_url}/api/embed"
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json={
                "model": model,
                "input": text
            })
            response.raise_for_status()
            data = response.json()
            
            embeddings = data.get("embeddings", [])
            if embeddings and len(embeddings) > 0:
                return embeddings[0]
                
    except httpx.HTTPStatusError as e:
        current_app.logger.error(f"Ollama embed API error: {e.response.text}")
    except Exception as e:
        current_app.logger.error(f"Error generating Ollama embedding: {e}")
    
    return None


def _generate_embedding_openai(text: str, model: str, api_key: str, base_url: str = None) -> Optional[List[float]]:
    """Génère un embedding via OpenAI ou API compatible."""
    url = base_url or "https://api.openai.com/v1"
    url = f"{url.rstrip('/')}/embeddings"
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "input": text
                }
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("data") and len(data["data"]) > 0:
                return data["data"][0].get("embedding")
                
    except httpx.HTTPStatusError as e:
        current_app.logger.error(f"OpenAI embed API error: {e.response.text}")
    except Exception as e:
        current_app.logger.error(f"Error generating OpenAI embedding: {e}")
    
    return None


def _generate_embedding_cohere(text: str, model: str, api_key: str) -> Optional[List[float]]:
    """Génère un embedding via Cohere."""
    url = "https://api.cohere.ai/v1/embed"
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "texts": [text],
                    "input_type": "search_document"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            embeddings = data.get("embeddings", [])
            if embeddings and len(embeddings) > 0:
                return embeddings[0]
                
    except httpx.HTTPStatusError as e:
        current_app.logger.error(f"Cohere embed API error: {e.response.text}")
    except Exception as e:
        current_app.logger.error(f"Error generating Cohere embedding: {e}")
    
    return None


def _get_provider_info(provider_id: str) -> Optional[Dict[str, Any]]:
    """Récupère les informations du provider depuis le ProviderManager."""
    try:
        from .provider_manager import get_provider_manager
        mgr = get_provider_manager()
        return mgr.get_provider(provider_id, include_api_key=True)
    except Exception as e:
        current_app.logger.error(f"Error getting provider info: {e}")
        return None


def generate_embedding(text: str, model: Optional[str] = None, provider_id: Optional[str] = None) -> Optional[List[float]]:
    """
    Génère un embedding pour un texte.
    
    Args:
        text: Texte à transformer en embedding
        model: Modèle à utiliser (optionnel, utilise config sinon)
        provider_id: ID du provider (optionnel, utilise config sinon)
        
    Returns:
        Liste de floats représentant l'embedding, ou None en cas d'erreur
    """
    embedding_model = model or get_embedding_model()
    embedding_provider_id = provider_id or get_embedding_provider_id()
    
    if not embedding_model:
        raise ValueError("No embedding model configured. Please configure one in settings.")
    
    # Si pas de provider configuré, utiliser Ollama par défaut
    if not embedding_provider_id:
        from ..utils import get_effective_ollama_base_url
        base_url = get_effective_ollama_base_url()
        return _generate_embedding_ollama(text, embedding_model, base_url)
    
    # Récupérer les infos du provider
    provider = _get_provider_info(embedding_provider_id)
    if not provider:
        current_app.logger.warning(f"Provider {embedding_provider_id} not found, falling back to Ollama")
        from ..utils import get_effective_ollama_base_url
        base_url = get_effective_ollama_base_url()
        return _generate_embedding_ollama(text, embedding_model, base_url)
    
    provider_type = provider.get("type", "")
    api_key = provider.get("api_key", "")
    base_url = provider.get("url", "")
    
    # Router vers le bon provider
    if provider_type == "ollama":
        return _generate_embedding_ollama(text, embedding_model, base_url or "http://localhost:11434")
    
    elif provider_type in ("openai", "openai_compatible", "groq", "mistral", "deepseek", "huggingface", "cerebras"):
        return _generate_embedding_openai(text, embedding_model, api_key, base_url)
    
    elif provider_type == "cohere":
        return _generate_embedding_cohere(text, embedding_model, api_key)
    
    else:
        current_app.logger.warning(f"Provider type {provider_type} not supported for embeddings, falling back to Ollama")
        from ..utils import get_effective_ollama_base_url
        return _generate_embedding_ollama(text, embedding_model, get_effective_ollama_base_url())


def generate_embeddings_batch(texts: List[str], model: Optional[str] = None, provider_id: Optional[str] = None) -> List[Optional[List[float]]]:
    """
    Génère des embeddings pour une liste de textes.
    
    Args:
        texts: Liste de textes
        model: Modèle à utiliser
        provider_id: ID du provider
        
    Returns:
        Liste d'embeddings (mêmes indices que texts)
    """
    embedding_model = model or get_embedding_model()
    embedding_provider_id = provider_id or get_embedding_provider_id()
    
    if not embedding_model:
        raise ValueError("No embedding model configured. Please configure one in settings.")
    
    # Récupérer les infos du provider
    provider = None
    if embedding_provider_id:
        provider = _get_provider_info(embedding_provider_id)
    
    provider_type = provider.get("type", "ollama") if provider else "ollama"
    
    # Pour Ollama, utiliser l'API batch native
    if provider_type == "ollama":
        base_url = provider.get("url") if provider else None
        if not base_url:
            from ..utils import get_effective_ollama_base_url
            base_url = get_effective_ollama_base_url()
        
        url = f"{base_url}/api/embed"
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, json={
                    "model": embedding_model,
                    "input": texts
                })
                response.raise_for_status()
                data = response.json()
                return data.get("embeddings", [])
                
        except Exception as e:
            current_app.logger.error(f"Error generating batch embeddings: {e}")
            # Fallback: générer un par un
            return [generate_embedding(text, embedding_model, embedding_provider_id) for text in texts]
    
    # Pour les autres providers, générer un par un (la plupart supportent le batch mais avec syntaxe différente)
    return [generate_embedding(text, embedding_model, embedding_provider_id) for text in texts]


def list_embedding_models(provider_id: Optional[str] = None) -> List[dict]:
    """
    Liste les modèles d'embedding disponibles pour un provider.
    
    Args:
        provider_id: ID du provider (optionnel, utilise Ollama si non spécifié)
    
    Returns:
        Liste de dicts avec info sur les modèles
    """
    # Si pas de provider spécifié, lister les modèles Ollama
    if not provider_id:
        return _list_ollama_embedding_models()
    
    provider = _get_provider_info(provider_id)
    if not provider:
        return []
    
    provider_type = provider.get("type", "")
    
    if provider_type == "ollama":
        base_url = provider.get("url", "http://localhost:11434")
        return _list_ollama_embedding_models(base_url)
    
    elif provider_type == "openai":
        return [
            {"name": "text-embedding-3-small", "dimensions": 1536, "description": "Fastest, cheapest"},
            {"name": "text-embedding-3-large", "dimensions": 3072, "description": "Best quality"},
            {"name": "text-embedding-ada-002", "dimensions": 1536, "description": "Legacy model"}
        ]
    
    elif provider_type == "cohere":
        return [
            {"name": "embed-english-v3.0", "dimensions": 1024, "description": "English only"},
            {"name": "embed-multilingual-v3.0", "dimensions": 1024, "description": "Multilingual (100+ languages)"},
            {"name": "embed-english-light-v3.0", "dimensions": 384, "description": "Faster, English only"},
            {"name": "embed-multilingual-light-v3.0", "dimensions": 384, "description": "Faster, multilingual"}
        ]
    
    elif provider_type in ("openai_compatible", "groq", "mistral", "deepseek"):
        # Pour ces providers, retourner une liste vide - l'utilisateur doit saisir le nom manuellement
        return []
    
    return []


def _list_ollama_embedding_models(base_url: str = None) -> List[dict]:
    """Liste les modèles d'embedding Ollama."""
    if not base_url:
        from ..utils import get_effective_ollama_base_url
        base_url = get_effective_ollama_base_url()
    
    url = f"{base_url}/api/tags"
    embedding_models = []
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            
            for model in data.get("models", []):
                name = model.get("name", "")
                # Heuristique: les modèles d'embedding ont souvent "embed" dans le nom
                is_embedding = any(kw in name.lower() for kw in ['embed', 'minilm', 'bge', 'e5', 'gte', 'arctic'])
                
                if is_embedding:
                    embedding_models.append({
                        'name': name,
                        'size': model.get('size', 0),
                        'dimensions': get_embedding_dimensions(name)
                    })
                    
    except Exception as e:
        current_app.logger.error(f"Error listing embedding models: {e}")
    
    return embedding_models
