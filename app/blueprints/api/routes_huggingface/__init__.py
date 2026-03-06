"""
API routes for HuggingFace model search and download
"""
from __future__ import annotations

import re
from flask import Blueprint, jsonify, request, current_app, Response
from markupsafe import escape

from ....services.huggingface_client import HuggingFaceClient
from ....services.tasks import enqueue_pull_gguf
from ....utils import get_effective_ollama_base_url


api_huggingface_bp = Blueprint("api_huggingface", __name__)


def hf_client() -> HuggingFaceClient:
    return HuggingFaceClient(
        hf_token=current_app.config.get("HF_TOKEN"),
        connect_timeout=current_app.config["HTTP_CONNECT_TIMEOUT"],
        read_timeout=current_app.config["HTTP_READ_TIMEOUT"],
    )


def _normalize_param_size(value: str) -> str:
    """Normalise une valeur saisie pour le filtre de nombre de paramètres."""
    v = (value or "").strip()
    if not v:
        return ""
    v = v.upper()
    if re.fullmatch(r"\d+(\.\d+)?B", v):
        return v
    if re.fullmatch(r"\d+(\.\d+)?", v):
        return v + "B"
    return v


# Import sub-modules to register routes on the blueprint
from . import search     # noqa: E402, F401
from . import tags       # noqa: E402, F401
from . import download   # noqa: E402, F401
