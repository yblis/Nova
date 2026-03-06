from __future__ import annotations

import re
import json
from flask import Blueprint, jsonify, request, current_app, Response
from markupsafe import escape
from ....extensions import cache
from ....services.ollama_client import OllamaClient
from ....services.tasks import enqueue_pull_model, enqueue_check_update, enqueue_eject_force
from ....utils import get_effective_ollama_base_url
from ....services.remote_search import model_details
from ....services.ollama_web import OllamaWebClient
from ....services.progress_bus import ProgressBus
from ....services.model_metadata_service import get_model_metadata, delete_model_metadata, refresh_model_metadata


api_models_bp = Blueprint("api_models", __name__)


def client() -> OllamaClient:
    return OllamaClient(
        base_url=get_effective_ollama_base_url(),
        connect_timeout=current_app.config["HTTP_CONNECT_TIMEOUT"],
        read_timeout=current_app.config["HTTP_READ_TIMEOUT"],
    )


def models_cache_key():
    """Generate a cache key that includes the effective Ollama base URL."""
    base_url = get_effective_ollama_base_url()
    qs = request.query_string.decode("utf-8")
    return f"models_list:{base_url}:{qs}"


def detect_model_capabilities(name: str, details: dict) -> list:
    """
    Detect model capabilities based on name patterns and details.
    Returns a list of capability strings: 'embedding', 'vision', 'tools', 'code', 'thinking'
    """
    capabilities = []
    name_lower = name.lower()
    families = details.get("families", []) if isinstance(details, dict) else []

    embedding_patterns = ['embed', 'bge-', 'bge:', 'all-minilm', 'snowflake-arctic', 'paraphrase', '/e5-', ':e5-', '/e5:', 'gte-', 'gte:', 'jina-']
    if any(p in name_lower for p in embedding_patterns):
        capabilities.append('embedding')

    families_lower = [f.lower() for f in families] if isinstance(families, list) else []
    vision_patterns = [
        'vision', 'llava', 'bakllava', 'moondream', 'minicpm-v', 'minicpm:v',
        'phi3-vision', 'phi-3-vision', 'phi3.5-vision',
        'granite-vision', 'llama-vision', 'llama3.2-vision',
        'gemma2-vision', 'pixtral', 'internvl', 'cogvlm', 'yi-vl',
        'qwen-vl', 'qwen2-vl', 'qwenvl', 'glm-4v', 'internlm-xcomposer',
        'deepseek-vl', 'monkey', 'idefics', 'fuyu', 'kosmos'
    ]
    if any(p in name_lower for p in vision_patterns) or 'clip' in families_lower:
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


# Import sub-modules to register routes on the blueprint
from . import listing      # noqa: E402, F401
from . import details      # noqa: E402, F401
from . import lifecycle    # noqa: E402, F401
from . import monitoring   # noqa: E402, F401
from . import downloads    # noqa: E402, F401

