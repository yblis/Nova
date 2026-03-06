"""
Fonctions utilitaires pour le catalogue LM Studio : fetch GitHub, fetch HuggingFace, détection capabilities.
"""
from __future__ import annotations

import re
import logging
from typing import Dict, Any, List
from . import _catalog_cache, CATALOG_URL, HUGGINGFACE_API_URL

logger = logging.getLogger(__name__)


def fetch_github_catalog() -> List[Dict[str, Any]]:
    """Récupère le catalogue depuis GitHub avec cache."""
    import time
    import httpx

    now = time.time()
    if _catalog_cache["data"] and _catalog_cache["expires_at"] > now:
        return _catalog_cache["data"]

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(CATALOG_URL)
            response.raise_for_status()
            data = response.json()
            _catalog_cache["data"] = data
            _catalog_cache["expires_at"] = now + 3600
            return data
    except Exception as e:
        logger.warning(f"Failed to fetch GitHub catalog: {e}")
        return _catalog_cache.get("data") or []


def fetch_huggingface_lmstudio(query: str = "", limit: int = 20, sort: str = "downloads") -> List[Dict[str, Any]]:
    """Recherche les modèles lmstudio-community sur HuggingFace."""
    import httpx

    try:
        params = {"filter": "gguf", "sort": sort, "direction": "-1", "limit": limit}
        if not query:
            params["author"] = "lmstudio-community"
        else:
            params["search"] = query

        with httpx.Client(timeout=15.0) as client:
            response = client.get(HUGGINGFACE_API_URL, params=params)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.warning(f"Failed to fetch HuggingFace models: {e}")
        return []


def detect_model_capabilities(name: str) -> list:
    """Detect model capabilities based on name patterns."""
    capabilities = []
    name_lower = name.lower()

    embedding_patterns = ['embed', 'bge-', 'bge:', 'all-minilm', 'snowflake-arctic', 'paraphrase', '/e5-', ':e5-', '/e5:', 'gte-', 'gte:', 'jina-']
    if any(p in name_lower for p in embedding_patterns):
        capabilities.append('embedding')

    vision_patterns = [
        'vision', 'llava', 'bakllava', 'moondream', 'minicpm-v', 'minicpm:v',
        'phi3-vision', 'phi-3-vision', 'phi3.5-vision',
        'granite-vision', 'llama-vision', 'llama3.2-vision',
        'gemma2-vision', 'pixtral', 'internvl', 'cogvlm', 'yi-vl',
        'qwen-vl', 'qwen2-vl', 'qwenvl', 'glm-4v', 'internlm-xcomposer',
        'deepseek-vl', 'monkey', 'idefics', 'fuyu', 'kosmos'
    ]
    if any(p in name_lower for p in vision_patterns):
        capabilities.append('vision')

    code_patterns = ['code', 'codellama', 'deepseek-coder', 'starcoder', 'codegemma', 'codestral', 'qwen2.5-coder']
    if any(p in name_lower for p in code_patterns):
        capabilities.append('code')

    tools_patterns = ['tools', '-fc', 'functionary', 'hermes-3', 'firefunction', 'nexusraven']
    if any(p in name_lower for p in tools_patterns):
        capabilities.append('tools')

    thinking_patterns = ['deepseek-r1', 'qwq', 'o1-', 'reflection']
    if any(p in name_lower for p in thinking_patterns):
        capabilities.append('thinking')

    return capabilities
