"""
Embedding Service - Génération d'embeddings via Ollama
"""

import httpx
from typing import List, Optional
from flask import current_app


def get_ollama_base_url() -> str:
    """Récupère l'URL de base d'Ollama depuis la config."""
    from ..utils import get_effective_ollama_base_url
    return get_effective_ollama_base_url()


def get_embedding_model() -> Optional[str]:
    """
    Récupère le modèle d'embedding configuré depuis Redis.
    
    Returns:
        Nom du modèle ou None si non configuré
    """
    try:
        if current_app.redis:
            model = current_app.redis.get("rag:embedding_model")
            if model:
                return model.decode('utf-8')
    except Exception:
        pass
    return None


def set_embedding_model(model_name: str) -> bool:
    """
    Configure le modèle d'embedding dans Redis.
    
    Args:
        model_name: Nom du modèle Ollama à utiliser
        
    Returns:
        True si succès
    """
    try:
        if current_app.redis:
            current_app.redis.set("rag:embedding_model", model_name)
            return True
    except Exception as e:
        current_app.logger.error(f"Error setting embedding model: {e}")
    return False


def get_embedding_dimensions(model_name: str) -> int:
    """
    Retourne le nombre de dimensions pour un modèle d'embedding connu.
    Si inconnu, retourne 768 par défaut.
    """
    known_dimensions = {
        'nomic-embed-text': 768,
        'all-minilm': 384,
        'mxbai-embed-large': 1024,
        'snowflake-arctic-embed': 1024,
        'bge-m3': 1024,
        'bge-large': 1024,
    }
    
    # Chercher correspondance partielle
    model_lower = model_name.lower()
    for key, dim in known_dimensions.items():
        if key in model_lower:
            return dim
    
    return 768  # Défaut


def generate_embedding(text: str, model: Optional[str] = None) -> Optional[List[float]]:
    """
    Génère un embedding pour un texte.
    
    Args:
        text: Texte à transformer en embedding
        model: Modèle à utiliser (optionnel, utilise config sinon)
        
    Returns:
        Liste de floats représentant l'embedding, ou None en cas d'erreur
    """
    embedding_model = model or get_embedding_model()
    
    if not embedding_model:
        raise ValueError("No embedding model configured. Please configure one in settings.")
    
    base_url = get_ollama_base_url()
    url = f"{base_url}/api/embed"
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json={
                "model": embedding_model,
                "input": text
            })
            response.raise_for_status()
            data = response.json()
            
            # L'API retourne "embeddings" (liste de listes)
            embeddings = data.get("embeddings", [])
            if embeddings and len(embeddings) > 0:
                return embeddings[0]
            
    except httpx.HTTPStatusError as e:
        current_app.logger.error(f"Ollama embed API error: {e.response.text}")
    except Exception as e:
        current_app.logger.error(f"Error generating embedding: {e}")
    
    return None


def generate_embeddings_batch(texts: List[str], model: Optional[str] = None) -> List[Optional[List[float]]]:
    """
    Génère des embeddings pour une liste de textes.
    
    Args:
        texts: Liste de textes
        model: Modèle à utiliser
        
    Returns:
        Liste d'embeddings (mêmes indices que texts)
    """
    embedding_model = model or get_embedding_model()
    
    if not embedding_model:
        raise ValueError("No embedding model configured. Please configure one in settings.")
    
    base_url = get_ollama_base_url()
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
        return [generate_embedding(text, model) for text in texts]


def list_embedding_models() -> List[dict]:
    """
    Liste les modèles d'embedding disponibles sur Ollama.
    Filtre les modèles qui sont de type 'embedding'.
    
    Returns:
        Liste de dicts avec info sur les modèles
    """
    base_url = get_ollama_base_url()
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
