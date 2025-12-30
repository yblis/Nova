"""
Service de recherche web via SearXNG.

Ce service permet d'effectuer des recherches web via une instance SearXNG
et de formater les résultats pour injection dans le contexte LLM.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import httpx
from flask import current_app


@dataclass
class SearchResult:
    """Représente un résultat de recherche."""
    title: str
    url: str
    snippet: str
    
    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


# Chemin du fichier de configuration
def _get_config_path() -> str:
    """Retourne le chemin du fichier de configuration."""
    try:
        return os.path.join(current_app.root_path, "data", "web_search.json")
    except RuntimeError:
        # Hors contexte Flask
        return os.path.join(os.path.dirname(__file__), "..", "data", "web_search.json")


def _load_config() -> Dict[str, Any]:
    """Charge la configuration depuis le fichier JSON."""
    config_path = _get_config_path()
    default_config = {
        "searxng_url": "",
        "max_results": 5,
        "timeout": 10
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge avec les valeurs par défaut
                return {**default_config, **loaded}
    except Exception:
        pass
    
    return default_config


def _save_config(config: Dict[str, Any]) -> bool:
    """Sauvegarde la configuration dans le fichier JSON."""
    config_path = _get_config_path()
    
    try:
        # Créer le répertoire si nécessaire
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Failed to save web search config: {e}")
        return False


def get_searxng_url() -> Optional[str]:
    """
    Récupère l'URL SearXNG depuis la configuration.
    
    Returns:
        L'URL du serveur SearXNG ou None si non configuré.
    """
    config = _load_config()
    url = config.get("searxng_url", "")
    return url if url else None


def set_searxng_url(url: str) -> bool:
    """
    Enregistre l'URL SearXNG dans la configuration.
    
    Args:
        url: L'URL du serveur SearXNG (ex: https://searx.example.com)
    
    Returns:
        True si la sauvegarde a réussi.
    """
    config = _load_config()
    config["searxng_url"] = url.rstrip("/") if url else ""
    return _save_config(config)


def get_config() -> Dict[str, Any]:
    """
    Récupère la configuration complète.
    
    Returns:
        Dictionnaire avec la configuration.
    """
    return _load_config()


def set_config(updates: Dict[str, Any]) -> bool:
    """
    Met à jour la configuration.
    
    Args:
        updates: Dictionnaire avec les valeurs à mettre à jour.
    
    Returns:
        True si la sauvegarde a réussi.
    """
    config = _load_config()
    config.update(updates)
    return _save_config(config)


def is_searxng_available() -> bool:
    """
    Vérifie si le serveur SearXNG est accessible.
    
    Returns:
        True si le serveur répond correctement.
    """
    url = get_searxng_url()
    if not url:
        return False
    
    try:
        with httpx.Client(timeout=5.0) as client:
            # Tester avec une requête simple
            response = client.get(f"{url}/search", params={"q": "test", "format": "json"})
            return response.status_code == 200
    except Exception:
        return False


def search_web(query: str, max_results: int = None) -> List[SearchResult]:
    """
    Effectue une recherche web via SearXNG.
    
    Args:
        query: La requête de recherche.
        max_results: Nombre maximum de résultats (défaut: config ou 5).
    
    Returns:
        Liste de SearchResult.
    
    Raises:
        ValueError: Si SearXNG n'est pas configuré.
        httpx.HTTPError: En cas d'erreur de requête.
    """
    url = get_searxng_url()
    if not url:
        raise ValueError("SearXNG URL not configured")
    
    config = _load_config()
    if max_results is None:
        max_results = config.get("max_results", 5)
    timeout = config.get("timeout", 10)
    
    results: List[SearchResult] = []
    
    try:
        with httpx.Client(timeout=float(timeout)) as client:
            response = client.get(
                f"{url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "language": "fr-FR",  # Préférence français
                    "safesearch": 0
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Parser les résultats SearXNG
            for item in data.get("results", [])[:max_results]:
                title = item.get("title", "").strip()
                item_url = item.get("url", "").strip()
                # SearXNG peut avoir "content" ou "snippet"
                snippet = item.get("content", item.get("snippet", "")).strip()
                
                if title and item_url:
                    results.append(SearchResult(
                        title=title,
                        url=item_url,
                        snippet=snippet[:500] if snippet else ""  # Limiter la taille
                    ))
    
    except httpx.TimeoutException:
        if current_app:
            current_app.logger.warning(f"SearXNG timeout for query: {query}")
        raise
    except Exception as e:
        if current_app:
            current_app.logger.error(f"SearXNG search error: {e}")
        raise
    
    return results


def format_search_context(results: List[SearchResult]) -> str:
    """
    Formate les résultats de recherche pour injection dans le prompt LLM.
    
    Args:
        results: Liste de SearchResult.
    
    Returns:
        Texte formaté pour le contexte LLM.
    """
    if not results:
        return ""
    
    lines = ["=== RÉSULTATS DE RECHERCHE WEB ===\n"]
    
    for i, result in enumerate(results, 1):
        lines.append(f"[{i}] {result.title}")
        lines.append(f"    URL: {result.url}")
        if result.snippet:
            # Nettoyer le snippet
            snippet = result.snippet.replace("\n", " ").strip()
            lines.append(f"    Extrait: {snippet}")
        lines.append("")
    
    lines.append("=== FIN DES RÉSULTATS ===\n")
    
    return "\n".join(lines)
