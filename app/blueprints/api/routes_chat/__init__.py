from __future__ import annotations

import json
import os
import uuid
import base64
from flask import Blueprint, jsonify, request, Response, current_app, stream_with_context
from ....services.chat_history_pg import ChatHistoryService
from ....services.llm_clients import get_active_client, get_client_for_provider
from ....services.llm_error_handler import LLMError
from ....services.debate_service import get_debate_service

api_chat_bp = Blueprint("api_chat", __name__)

# Maximum file size for uploads (10 MB for text, 50 MB for PDF)
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_PDF_SIZE = 50 * 1024 * 1024

# Allowed file extensions for text extraction
ALLOWED_TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.ts', '.json', '.csv', '.html', '.css', '.yaml', '.yml', '.xml', '.sql', '.sh', '.bash', '.zsh', '.java', '.c', '.cpp', '.h', '.hpp', '.go', '.rs', '.rb', '.php', '.swift', '.kt'}


def get_history_service() -> ChatHistoryService:
    # PostgreSQL-based service (no data_dir needed)
    return ChatHistoryService()


def get_llm_client(model: str = None, provider_id: str = None):
    """Retourne le client LLM approprié.
    
    Args:
        model: Nom du modèle (si format Ollama 'name:tag', route vers Ollama)
        provider_id: ID du provider spécifique à utiliser (optionnel)
    """
    from ....services.provider_manager import get_provider_manager
    
    mgr = get_provider_manager()
    
    # 1. Provider explicitement demandé
    if provider_id:
        provider = mgr.get_provider(provider_id, include_api_key=True)
        if provider:
            return get_client_for_provider(provider)
    
    # 2. Si le modèle ressemble à un modèle Ollama (contient ':' comme llama3:8b)
    #    router vers le premier provider Ollama joignable
    if model and ':' in model:
        providers = mgr.get_providers(include_api_key_masked=False)
        for p in providers:
            if p.get("type") == "ollama" and p.get("url"):
                full_provider = mgr.get_provider(p["id"], include_api_key=True)
                if full_provider:
                    return get_client_for_provider(full_provider)
    
    # 3. Provider actif par défaut
    try:
        return get_active_client()
    except ValueError:
        from ....services.ollama_client import OllamaClient
        from ....utils import get_effective_ollama_base_url
        return OllamaClient(
            base_url=get_effective_ollama_base_url(),
            connect_timeout=current_app.config.get("HTTP_CONNECT_TIMEOUT", 10),
            read_timeout=current_app.config.get("HTTP_READ_TIMEOUT", 300),
        )


def generate_title(first_message: str, model: str) -> str:
    """Génère un titre court basé sur le premier message de l'utilisateur."""
    try:
        client = get_llm_client(model=model)
        prompt = f"Génère un titre court (maximum 5 mots) pour cette conversation. Réponds uniquement avec le titre, sans guillemets ni ponctuation. Message: {first_message[:200]}"
        messages = [{"role": "user", "content": prompt}]
        response = client.chat(messages=messages, model=model, stream=False)
        if "message" in response:
            title = response["message"].get("content", "").strip()
        else:
            title = response.get('response', '').strip()
        title = title.strip('"\'«»')
        if len(title) > 50:
            title = title[:47] + "..."
        return title if title else first_message[:30] + "..."
    except Exception as e:
        current_app.logger.warning(f"Failed to generate title: {e}")
        return first_message[:30] + "..." if len(first_message) > 30 else first_message


# Import sub-modules to register routes on the blueprint
from . import sessions     # noqa: E402, F401
from . import rag          # noqa: E402, F401
from . import generation   # noqa: E402, F401
from . import debate       # noqa: E402, F401
from . import memory       # noqa: E402, F401
