"""
Model Metadata Service - Gestion du cache des métadonnées des modèles Ollama

Ce service récupère les informations détaillées des modèles depuis l'API Ollama
et les stocke en cache Redis pour éviter des appels répétés.
"""

import json
import time
from typing import Optional, Dict, List, Any
from flask import current_app


def get_redis():
    """Récupère l'instance Redis depuis l'application Flask."""
    return getattr(current_app, 'redis', None)


def get_cache_key(model_name: str) -> str:
    """Génère la clé de cache pour un modèle."""
    return f"model_meta:{model_name}"


def detect_capabilities_from_metadata(metadata: Dict[str, Any]) -> List[str]:
    """
    Détecte les capacités d'un modèle à partir de ses métadonnées réelles.
    
    Args:
        metadata: Dictionnaire contenant les métadonnées du modèle
        
    Returns:
        Liste des capacités détectées: 'embedding', 'vision', 'code', 'tools', 'thinking'
    """
    capabilities = []
    
    families = metadata.get("families", [])
    families_lower = [f.lower() for f in families] if families else []
    model_name = metadata.get("name", "").lower()
    
    # Vision models - détection par "clip" dans families
    if "clip" in families_lower:
        capabilities.append("vision")
    
    # Embedding models - peuvent être détectés par le nom ou d'autres patterns
    embedding_patterns = ['embed', 'bge-', 'bge:', 'all-minilm', 'snowflake-arctic', 
                          'paraphrase', '/e5-', ':e5-', '/e5:', 'gte-', 'gte:', 'jina-']
    if any(p in model_name for p in embedding_patterns):
        capabilities.append('embedding')
    
    # Code models
    code_patterns = ['code', 'codellama', 'deepseek-coder', 'starcoder', 'codegemma', 
                     'codestral', 'qwen2.5-coder']
    if any(p in model_name for p in code_patterns):
        capabilities.append('code')
    
    # Tools/Function calling models
    tools_patterns = ['tools', '-fc', 'functionary', 'hermes-3', 'firefunction', 'nexusraven']
    if any(p in model_name for p in tools_patterns):
        capabilities.append('tools')
    
    # Thinking/Reasoning models
    thinking_patterns = ['deepseek-r1', 'qwq', 'qwen3', 'o1-', 'o3-', 'reflection']
    if any(p in model_name for p in thinking_patterns):
        capabilities.append('thinking')
    
    return capabilities


def get_model_metadata(model_name: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """
    Récupère les métadonnées d'un modèle depuis le cache ou l'API Ollama.
    
    Args:
        model_name: Nom du modèle
        force_refresh: Force la récupération depuis l'API même si les données sont en cache
        
    Returns:
        Dictionnaire avec les métadonnées du modèle ou None si erreur
    """
    redis = get_redis()
    cache_key = get_cache_key(model_name)
    
    # Essayer de récupérer depuis le cache
    if redis and not force_refresh:
        try:
            cached = redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return data
        except Exception as e:
            print(f"[ModelMetadata] Cache read error for {model_name}: {e}")
    
    # Récupérer depuis l'API Ollama
    return refresh_model_metadata(model_name)


def refresh_model_metadata(model_name: str) -> Optional[Dict[str, Any]]:
    """
    Récupère les métadonnées depuis l'API Ollama et ollama.com, puis met à jour le cache.
    
    Args:
        model_name: Nom du modèle
        
    Returns:
        Dictionnaire avec les métadonnées du modèle ou None si erreur
    """
    from .ollama_client import OllamaClient
    from ..utils import get_effective_ollama_base_url
    
    redis = get_redis()
    cache_key = get_cache_key(model_name)
    
    try:
        client = OllamaClient(
            base_url=get_effective_ollama_base_url(),
            connect_timeout=10.0,
            read_timeout=30.0
        )
        
        # Appeler l'API /api/show
        show_data = client.show(model_name)
        
        if not show_data:
            return None
        
        details = show_data.get("details", {})
        
        # Construire les métadonnées de base
        metadata = {
            "name": model_name,
            "families": details.get("families", []),
            "family": details.get("family", ""),
            "parameter_size": details.get("parameter_size", ""),
            "quantization_level": details.get("quantization_level", ""),
            "format": details.get("format", ""),
            "cached_at": int(time.time())
        }
        
        # Détecter les capacités depuis l'API locale (clip dans families)
        capabilities = detect_capabilities_from_metadata(metadata)
        
        # Si pas de capacités détectées, essayer de récupérer depuis ollama.com
        if not capabilities or "vision" not in capabilities:
            web_capabilities = _fetch_capabilities_from_web(model_name)
            if web_capabilities:
                # Fusionner les capacités
                for cap in web_capabilities:
                    if cap not in capabilities:
                        capabilities.append(cap)
                print(f"[ModelMetadata] Added capabilities from ollama.com for {model_name}: {web_capabilities}")
        
        metadata["capabilities"] = capabilities
        
        # Sauvegarder en cache Redis (expire après 7 jours)
        if redis:
            try:
                redis.setex(cache_key, 7 * 24 * 3600, json.dumps(metadata))
                print(f"[ModelMetadata] Cached metadata for {model_name}: {metadata['capabilities']}")
            except Exception as e:
                print(f"[ModelMetadata] Cache write error for {model_name}: {e}")
        
        return metadata
        
    except Exception as e:
        print(f"[ModelMetadata] Error fetching metadata for {model_name}: {e}")
        return None


def _fetch_capabilities_from_web(model_name: str) -> List[str]:
    """
    Récupère les capacités d'un modèle depuis ollama.com
    
    Args:
        model_name: Nom du modèle (peut inclure le tag, ex: "llava:7b")
        
    Returns:
        Liste des capacités détectées depuis ollama.com
    """
    try:
        from .ollama_web import OllamaWebClient
        
        # Extraire le nom de base du modèle (sans le tag)
        base_name = model_name.split(":")[0]
        
        web_client = OllamaWebClient(timeout=5.0)
        
        # Rechercher le modèle sur ollama.com
        results = web_client.search_models(base_name)
        
        # Trouver le modèle correspondant
        for model in results:
            if model.get("name", "").lower() == base_name.lower():
                caps = model.get("capabilities", [])
                if caps:
                    return caps
        
        # Si pas trouvé exactement, chercher dans les résultats partiels
        for model in results:
            if base_name.lower() in model.get("name", "").lower():
                caps = model.get("capabilities", [])
                if caps:
                    return caps
        
        return []
        
    except Exception as e:
        print(f"[ModelMetadata] Error fetching from ollama.com for {model_name}: {e}")
        return []


def delete_model_metadata(model_name: str) -> bool:
    """
    Supprime les métadonnées d'un modèle du cache.
    
    Args:
        model_name: Nom du modèle
        
    Returns:
        True si supprimé, False sinon
    """
    redis = get_redis()
    if not redis:
        return False
    
    cache_key = get_cache_key(model_name)
    
    try:
        redis.delete(cache_key)
        print(f"[ModelMetadata] Deleted metadata for {model_name}")
        return True
    except Exception as e:
        print(f"[ModelMetadata] Error deleting metadata for {model_name}: {e}")
        return False


def get_all_cached_metadata() -> Dict[str, Dict[str, Any]]:
    """
    Récupère toutes les métadonnées en cache.
    
    Returns:
        Dictionnaire {model_name: metadata}
    """
    redis = get_redis()
    if not redis:
        return {}
    
    result = {}
    try:
        # Récupérer toutes les clés de métadonnées
        keys = redis.keys("model_meta:*")
        for key in keys:
            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
            model_name = key_str.replace("model_meta:", "")
            cached = redis.get(key)
            if cached:
                result[model_name] = json.loads(cached)
    except Exception as e:
        print(f"[ModelMetadata] Error fetching all metadata: {e}")
    
    return result
