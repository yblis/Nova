"""
API routes for LM Studio model discovery and download
"""
from __future__ import annotations

import re
import logging
from typing import Dict, Any, List, Optional
from flask import Blueprint, jsonify, request, Response, url_for, current_app
from markupsafe import escape

from ....services.provider_manager import ProviderManager
from ....services.llm_clients import get_client_for_provider


api_lmstudio_bp = Blueprint("api_lmstudio", __name__)
logger = logging.getLogger(__name__)

# Cache du catalogue GitHub (TTL 1 heure)
_catalog_cache: Dict[str, Any] = {"data": None, "expires_at": 0}
CATALOG_URL = "https://raw.githubusercontent.com/lmstudio-ai/model-catalog/main/catalog.json"
HUGGINGFACE_API_URL = "https://huggingface.co/api/models"


def _get_lmstudio_client():
    """Récupère le client LM Studio s'il est configuré."""
    data_path = current_app.root_path + "/data/providers.json"
    provider_manager = ProviderManager(data_path)
    provider = provider_manager.get_provider("lmstudio")
    if not provider:
        return None
    provider_dict = {
        "type": "lmstudio",
        "url": provider.get("base_url", "http://localhost:1234/v1"),
        "api_key": provider.get("api_key", "")
    }
    return get_client_for_provider(provider_dict)


def _format_size(size_bytes: int) -> str:
    """Formate une taille en bytes en format lisible."""
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.1f} GB"
    elif size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"
    else:
        return f"{size_bytes / 1_000:.1f} KB"


def _format_downloads(downloads: int) -> str:
    """Formate le nombre de téléchargements."""
    if downloads >= 1_000_000:
        return f"{downloads / 1_000_000:.1f}M"
    elif downloads >= 1_000:
        return f"{downloads / 1_000:.1f}K"
    return str(downloads)


# Import sub-modules to register routes on the blueprint
from . import catalog    # noqa: E402, F401
from . import search     # noqa: E402, F401
from . import download   # noqa: E402, F401
