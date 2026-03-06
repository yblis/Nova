"""
Service d'intégration Bookstack.

Ce service permet d'interroger un serveur Bookstack pour récupérer
de la documentation et la formater pour injection dans le contexte LLM.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import re
import httpx
from flask import current_app


@dataclass
class BookstackResult:
    """Représente un résultat de recherche Bookstack."""
    title: str
    url: str
    content: str
    type: str  # page, chapter, book, bookshelf
    book_name: str = ""

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


# ======= Configuration persistence (JSON file) =======

def _get_config_path() -> str:
    """Retourne le chemin du fichier de configuration."""
    try:
        return os.path.join(current_app.root_path, "data", "bookstack.json")
    except RuntimeError:
        return os.path.join(os.path.dirname(__file__), "..", "data", "bookstack.json")


def _load_config() -> Dict[str, Any]:
    """Charge la configuration depuis le fichier JSON."""
    default_config = {
        "url": "",
        "token_id": "",
        "token_secret": "",
        "max_results": 5,
        "timeout": 15
    }

    try:
        config_path = _get_config_path()
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                return {**default_config, **loaded}
    except Exception:
        pass

    return default_config


def _save_config(config: Dict[str, Any]) -> bool:
    """Sauvegarde la configuration dans le fichier JSON."""
    config_path = _get_config_path()

    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f"Failed to save Bookstack config: {e}")
        except RuntimeError:
            pass
        return False


# ======= Public API =======

def get_config() -> Dict[str, Any]:
    """
    Récupère la configuration complète.
    Le token_secret est masqué pour la sécurité.
    """
    config = _load_config()
    # Masquer le token_secret dans la réponse
    secret = config.get("token_secret", "")
    config["token_secret_masked"] = ("●" * 8 + secret[-4:]) if len(secret) > 4 else ("●" * len(secret) if secret else "")
    return config


def set_config(updates: Dict[str, Any]) -> bool:
    """
    Met à jour la configuration.

    Args:
        updates: Dictionnaire avec les valeurs à mettre à jour.

    Returns:
        True si la sauvegarde a réussi.
    """
    config = _load_config()

    if "url" in updates:
        config["url"] = updates["url"].rstrip("/") if updates["url"] else ""
    if "token_id" in updates:
        config["token_id"] = updates["token_id"].strip() if updates["token_id"] else ""
    if "token_secret" in updates:
        config["token_secret"] = updates["token_secret"].strip() if updates["token_secret"] else ""
    if "max_results" in updates:
        try:
            config["max_results"] = max(1, min(20, int(updates["max_results"])))
        except (ValueError, TypeError):
            pass
    if "timeout" in updates:
        try:
            config["timeout"] = max(1, min(60, int(updates["timeout"])))
        except (ValueError, TypeError):
            pass

    return _save_config(config)


def _get_auth_headers() -> Dict[str, str]:
    """Retourne les headers d'authentification Bookstack."""
    config = _load_config()
    token_id = config.get("token_id", "")
    token_secret = config.get("token_secret", "")
    if not token_id or not token_secret:
        return {}
    return {"Authorization": f"Token {token_id}:{token_secret}"}


def is_bookstack_available() -> bool:
    """
    Vérifie si Bookstack est configuré (URL + tokens renseignés).
    Ne fait PAS d'appel HTTP live — utilisez test_connection() pour cela.

    Returns:
        True si la configuration est complète.
    """
    config = _load_config()
    url = config.get("url", "")
    token_id = config.get("token_id", "")
    token_secret = config.get("token_secret", "")

    return bool(url and token_id and token_secret)


def test_connection() -> Dict[str, Any]:
    """
    Teste la connexion au serveur Bookstack.

    Returns:
        Dictionnaire avec {ok: bool, message: str, results_count: int}
    """
    config = _load_config()
    url = config.get("url", "")
    token_id = config.get("token_id", "")
    token_secret = config.get("token_secret", "")

    if not url:
        return {"ok": False, "message": "URL du serveur Bookstack non configurée"}
    if not token_id or not token_secret:
        return {"ok": False, "message": "Token ID et Token Secret requis"}

    try:
        headers = _get_auth_headers()
        with httpx.Client(timeout=10.0, verify=False) as client:
            response = client.get(
                f"{url}/api/search",
                params={"query": "test", "count": 1},
                headers=headers
            )

            if response.status_code == 401:
                return {"ok": False, "message": "Authentification échouée — vérifiez vos tokens API"}
            if response.status_code == 403:
                return {"ok": False, "message": "Accès refusé — le rôle de l'utilisateur n'a pas la permission 'Access System API'"}

            response.raise_for_status()
            data = response.json()
            total = data.get("total", 0)

            return {
                "ok": True,
                "message": f"Connexion réussie ! {total} résultat(s) trouvé(s) dans Bookstack.",
                "results_count": total
            }

    except httpx.TimeoutException:
        return {"ok": False, "message": f"Timeout — le serveur {url} ne répond pas dans les 10 secondes"}
    except httpx.ConnectError:
        return {"ok": False, "message": f"Impossible de se connecter à {url} — vérifiez l'URL et le réseau"}
    except Exception as e:
        return {"ok": False, "message": f"Erreur de connexion : {str(e)}"}


def _strip_html(html: str) -> str:
    """Retire les tags HTML et nettoie le texte."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def search_bookstack(query: str, max_results: int = None) -> List[BookstackResult]:
    """
    Recherche dans Bookstack via l'API.

    Args:
        query: La requête de recherche.
        max_results: Nombre maximum de résultats.

    Returns:
        Liste de BookstackResult.
    """
    config = _load_config()
    url = config.get("url", "")

    if not url:
        raise ValueError("Bookstack URL not configured")

    headers = _get_auth_headers()
    if not headers:
        raise ValueError("Bookstack API tokens not configured")

    if max_results is None:
        max_results = config.get("max_results", 5)
    timeout = config.get("timeout", 15)

    results: List[BookstackResult] = []

    try:
        with httpx.Client(timeout=float(timeout), verify=False) as client:
            response = client.get(
                f"{url}/api/search",
                params={"query": query, "count": max_results},
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("data", [])[:max_results]:
                item_type = item.get("type", "page")
                title = item.get("name", "").strip()
                item_url = item.get("url", "").strip()
                # Preview text or HTML content
                preview = item.get("preview_html", {})
                if isinstance(preview, dict):
                    content_html = preview.get("content", "")
                else:
                    content_html = str(preview)

                content = _strip_html(content_html)

                # Fallback: use item tags/url for context
                book_name = ""
                tags = item.get("tags", [])
                if tags and isinstance(tags, list):
                    book_name = ", ".join(t.get("name", "") for t in tags[:3] if t.get("name"))

                if title:
                    results.append(BookstackResult(
                        title=title,
                        url=item_url or f"{url}",
                        content=content[:2000] if content else "",
                        type=item_type,
                        book_name=book_name
                    ))

    except httpx.TimeoutException:
        try:
            current_app.logger.warning(f"Bookstack timeout for query: {query}")
        except RuntimeError:
            pass
        raise
    except Exception as e:
        try:
            current_app.logger.error(f"Bookstack search error: {e}")
        except RuntimeError:
            pass
        raise

    return results


def format_bookstack_context(results: List[BookstackResult]) -> str:
    """
    Formate les résultats Bookstack pour injection dans le prompt LLM.

    Args:
        results: Liste de BookstackResult.

    Returns:
        Texte formaté pour le contexte LLM.
    """
    if not results:
        return ""

    lines = ["=== DOCUMENTATION BOOKSTACK ===\n"]

    for i, result in enumerate(results, 1):
        type_label = {"page": "Page", "chapter": "Chapitre", "book": "Livre", "bookshelf": "Étagère"}.get(result.type, result.type)
        lines.append(f"[{i}] {type_label}: {result.title}")
        if result.book_name:
            lines.append(f"    Livre: {result.book_name}")
        lines.append(f"    URL: {result.url}")
        if result.content:
            content = result.content.replace("\n", " ").strip()
            lines.append(f"    Contenu: {content}")
        lines.append("")

    lines.append("=== FIN DE LA DOCUMENTATION ===\n")

    return "\n".join(lines)
