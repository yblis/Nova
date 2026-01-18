
import json
import os
import uuid
import base64
from flask import Blueprint, jsonify, request, Response, current_app, stream_with_context
from ...services.chat_history_pg import ChatHistoryService
from ...services.llm_clients import get_active_client, get_client_for_provider
from ...services.llm_error_handler import LLMError
from ...services.debate_service import get_debate_service

api_chat_bp = Blueprint("api_chat", __name__)

# Maximum file size for uploads (10 MB for text, 50 MB for PDF)
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_PDF_SIZE = 50 * 1024 * 1024

# Allowed file extensions for text extraction
ALLOWED_TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.ts', '.json', '.csv', '.html', '.css', '.yaml', '.yml', '.xml', '.sql', '.sh', '.bash', '.zsh', '.java', '.c', '.cpp', '.h', '.hpp', '.go', '.rs', '.rb', '.php', '.swift', '.kt'}

def get_history_service() -> ChatHistoryService:
    # PostgreSQL-based service (no data_dir needed)
    return ChatHistoryService()

def get_llm_client():
    """Retourne le client LLM pour le fournisseur actif."""
    try:
        return get_active_client()
    except ValueError:
        # Fallback pour rétrocompatibilité - si aucun provider, essayer Ollama
        from ...services.ollama_client import OllamaClient
        from ...utils import get_effective_ollama_base_url
        return OllamaClient(
            base_url=get_effective_ollama_base_url(),
            connect_timeout=current_app.config.get("HTTP_CONNECT_TIMEOUT", 10),
            read_timeout=current_app.config.get("HTTP_READ_TIMEOUT", 300),
        )

def generate_title(first_message: str, model: str) -> str:
    """
    Génère un titre court basé sur le premier message de l'utilisateur.
    
    Args:
        first_message: Le premier message de l'utilisateur
        model: Le modèle LLM à utiliser
    
    Returns:
        Un titre court (max 50 caractères)
    """
    try:
        client = get_llm_client()
        prompt = f"Génère un titre court (maximum 5 mots) pour cette conversation. Réponds uniquement avec le titre, sans guillemets ni ponctuation. Message: {first_message[:200]}"
        
        # Utiliser chat au lieu de generate pour compatibilité multi-provider
        messages = [{"role": "user", "content": prompt}]
        response = client.chat(messages=messages, model=model, stream=False)
        # Extraire le contenu de la réponse (format unifié)
        if "message" in response:
            title = response["message"].get("content", "").strip()
        else:
            title = response.get('response', '').strip()
        # Nettoyer le titre (enlever guillemets, ponctuation excessive)
        title = title.strip('"\'«»')
        # Limiter à 50 caractères
        if len(title) > 50:
            title = title[:47] + "..."
        return title if title else first_message[:30] + "..."
    except Exception as e:
        current_app.logger.warning(f"Failed to generate title: {e}")
        return first_message[:30] + "..." if len(first_message) > 30 else first_message

@api_chat_bp.route("/chat/sessions", methods=["GET"])
def list_sessions():
    """List all chat sessions"""
    svc = get_history_service()
    return jsonify({"sessions": svc.list_sessions()})

@api_chat_bp.route("/chat/sessions", methods=["POST"])
def create_session():
    """Create a new chat session"""
    svc = get_history_service()
    data = request.json or {}
    model = data.get("model", "llama3")
    title = data.get("title", "New Chat")
    
    session_id = svc.create_session(model, title)
    session = svc.get_session(session_id)
    return jsonify(session)

@api_chat_bp.route("/chat/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    """Get messages for a specific session"""
    svc = get_history_service()
    session = svc.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session)

@api_chat_bp.route("/chat/sessions/<session_id>", methods=["PATCH"])
def update_session(session_id):
    """Update session settings (system_prompt, model_config, title)"""
    svc = get_history_service()
    data = request.json or {}
    
    try:
        updated = svc.update_session_settings(
            session_id,
            system_prompt=data.get("system_prompt"),
            model_config=data.get("model_config"),
            title=data.get("title")
        )
        return jsonify(updated)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

@api_chat_bp.route("/chat/sessions/<session_id>/pin", methods=["POST"])
def toggle_session_pin(session_id):
    """Toggle the pinned status of a session"""
    svc = get_history_service()
    try:
        new_status = svc.toggle_session_pin(session_id)
        return jsonify({"is_pinned": new_status})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

@api_chat_bp.route("/chat/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """Delete a session and its associated RAG documents"""
    svc = get_history_service()
    
    # Delete RAG documents first
    try:
        from ...services.rag_service import delete_session_documents
        delete_session_documents(session_id)
    except Exception as e:
        current_app.logger.warning(f"Could not delete RAG documents: {e}")
    
    svc.delete_session(session_id)
    return jsonify({"status": "deleted"})

@api_chat_bp.route("/chat/sessions/bulk", methods=["DELETE"])
def delete_sessions_bulk():
    """Delete multiple sessions by their IDs"""
    svc = get_history_service()
    data = request.json or {}
    session_ids = data.get("session_ids", [])
    
    if not session_ids:
        return jsonify({"error": "session_ids required"}), 400
    
    # Delete RAG documents for each session
    try:
        from ...services.rag_service import delete_session_documents
        for session_id in session_ids:
            try:
                delete_session_documents(session_id)
            except Exception as e:
                current_app.logger.warning(f"Could not delete RAG documents for {session_id}: {e}")
    except Exception as e:
        current_app.logger.warning(f"Could not import RAG service: {e}")
    
    deleted_count = svc.delete_sessions(session_ids)
    return jsonify({"status": "deleted", "deleted_count": deleted_count})

@api_chat_bp.route("/chat/sessions/all", methods=["DELETE"])
def delete_all_sessions():
    """Delete all sessions and their associated RAG documents"""
    svc = get_history_service()
    
    # Get all sessions first to delete their RAG documents
    sessions = svc.list_sessions()
    
    # Delete RAG documents for each session
    try:
        from ...services.rag_service import delete_session_documents
        for session in sessions:
            try:
                delete_session_documents(session["id"])
            except Exception as e:
                current_app.logger.warning(f"Could not delete RAG documents for {session['id']}: {e}")
    except Exception as e:
        current_app.logger.warning(f"Could not import RAG service: {e}")
    
    deleted_count = svc.delete_all_sessions()
    return jsonify({"status": "deleted", "deleted_count": deleted_count})

@api_chat_bp.route("/chat/upload", methods=["POST"])
def upload_file():
    """
    Handle file upload, extract text content.
    Returns: {"content": "...", "filename": "...", "type": "..."}
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_FILE_SIZE:
        return jsonify({"error": f"File too large. Maximum size is {MAX_FILE_SIZE // 1024 // 1024} MB"}), 400
    
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    
    # Check if it's an allowed text file
    if ext not in ALLOWED_TEXT_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_TEXT_EXTENSIONS))}"}), 400
    
    try:
        # Read and decode the file content
        content = file.read().decode('utf-8', errors='replace')
        return jsonify({
            "content": content,
            "filename": filename,
            "type": ext[1:] if ext else "txt",  # Remove dot from extension
            "size": size
        })
    except Exception as e:
        return jsonify({"error": f"Failed to read file: {str(e)}"}), 500


# ============== RAG / PDF Endpoints ==============

@api_chat_bp.route("/chat/upload-pdf", methods=["POST"])
def upload_pdf():
    """
    Upload a PDF file and index it for RAG.
    Uses intelligent OCR for scanned PDFs.
    Expects: multipart form with 'file' (PDF) and 'session_id'
    """
    from ...services.ocr_service import process_pdf_intelligent, get_pdf_info_extended
    from ...services.embedding_service import generate_embeddings_batch, get_embedding_model, get_embedding_dimensions
    from ...services.rag_service import store_document, init_db
    from ...services.rag_config_service import get_setting
    
    # Validate request
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    session_id = request.form.get('session_id')
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    filename = file.filename
    if not filename.lower().endswith('.pdf'):
        return jsonify({"error": "Only PDF files are allowed"}), 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_PDF_SIZE:
        return jsonify({"error": f"File too large. Maximum size is {MAX_PDF_SIZE // 1024 // 1024} MB"}), 400
    
    # Check if embedding model is configured
    embedding_model = get_embedding_model()
    if not embedding_model:
        return jsonify({
            "error": "No embedding model configured. Please configure one in Settings > RAG."
        }), 400
    
    try:
        # Initialize RAG database
        init_db()
        
        # Save PDF file immediately
        uploads_dir = current_app.config.get("RAG_UPLOADS_DIR", "/app/rag_uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        
        file_id = str(uuid.uuid4())
        file_path = os.path.join(uploads_dir, f"{file_id}.pdf")
        
        file.save(file_path)
        
        # Create 'pending' document entry in DB
        doc_id = store_document(
            session_id=session_id,
            filename=filename,
            file_path=file_path,
            chunks=None, # No chunks yet
            embeddings=None,
            embedding_model=embedding_model,
            embedding_dimensions=None,
            status='pending'
        )

        try:
            # Enqueue background task
            if hasattr(current_app, 'rq') and current_app.rq:
                from ...tasks.rag_tasks import process_document_background
                job = current_app.rq.enqueue(
                    process_document_background,
                    args=(doc_id, session_id, filename, file_path),
                    job_timeout=current_app.config.get("RQ_DEFAULT_JOB_TIMEOUT", 3600)
                )
                current_app.logger.info(f"Enqueued PDF processing job {job.id} for doc {doc_id}")
            else:
                # Fallback synchrone si RQ n'est pas dispo (dev)
                current_app.logger.warning("RQ not available, falling back to synchronous processing")
                from ...tasks.rag_tasks import process_document_background
                process_document_background(doc_id, session_id, filename, file_path)
        
        except Exception as e:
            current_app.logger.error(f"Failed to enqueue task: {e}")
            # Si le enqueue plante, on peut le faire en synchrone ou juste fail
            return jsonify({"error": "Failed to start processing"}), 500

        return jsonify({
            "message": "File uploaded and processing started",
            "document_id": doc_id,
            "status": "pending"
        })

    except Exception as e:
        current_app.logger.error(f"Error uploading PDF: {e}")
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500


@api_chat_bp.route("/chat/sessions/<session_id>/documents", methods=["GET"])
def list_session_documents(session_id):
    """List all RAG documents attached to a session"""
    from ...services.rag_service import list_documents, init_db
    
    try:
        init_db()
        documents = list_documents(session_id)
        return jsonify({"documents": documents})
    except Exception as e:
        current_app.logger.error(f"Error listing documents: {e}")
        return jsonify({"documents": []})


@api_chat_bp.route("/rag/documents/<document_id>/chunks", methods=["GET"])
def list_document_chunks(document_id):
    """List chunks and stats for a specific document"""
    from ...services.rag_service import get_document_chunks, get_document_stats
    
    chunks = get_document_chunks(document_id)
    stats = get_document_stats(document_id)
    
    return jsonify({
        "chunks": chunks,
        "stats": stats
    })


@api_chat_bp.route("/rag/chunks/<chunk_id>", methods=["DELETE"])
def delete_chunk_route(chunk_id):
    """Delete a specific chunk"""
    from ...services.rag_service import delete_chunk as svc_delete_chunk
    
    if svc_delete_chunk(chunk_id):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Failed to delete chunk"}), 500


@api_chat_bp.route("/rag/documents/<document_id>/search", methods=["POST"])
def search_in_document(document_id):
    """Search chunks within a specific document"""
    from ...services.rag_service import search_similar, get_document_metadata
    from ...services.embedding_service import generate_embedding
    
    data = request.json or {}
    query = data.get("query", "").strip()
    
    if not query:
        return jsonify({"error": "Query required"}), 400
        
    # Get session_id from document
    doc_meta = get_document_metadata(document_id)
    if not doc_meta:
        return jsonify({"error": "Document not found"}), 404
        
    session_id = doc_meta["session_id"]
    
    try:
        query_embedding = generate_embedding(query)
        if not query_embedding:
            return jsonify({"error": "Failed to generate embedding"}), 500
            
        chunks = search_similar(
            session_id=session_id,
            query_embedding=query_embedding,
            top_k=20,
            document_id=document_id
        )
        
        return jsonify({"results": chunks})
        
    except Exception as e:
        current_app.logger.error(f"Error searching document chunks: {e}")
        return jsonify({"error": str(e)}), 500


@api_chat_bp.route("/chat/documents/<document_id>", methods=["DELETE"])
def delete_document(document_id):
    """Delete a RAG document"""
    from ...services.rag_service import delete_document as rag_delete_document
    
    try:
        success = rag_delete_document(document_id)
        if success:
            return jsonify({"status": "deleted"})
        return jsonify({"error": "Document not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error deleting document: {e}")
        return jsonify({"error": str(e)}), 500


@api_chat_bp.route("/rag/ocr-providers", methods=["GET"])
def get_ocr_providers():
    """
    List configured LLM providers that can be used for OCR.
    Returns list of providers with id, name, and type.
    """
    from ...services.provider_manager import get_provider_manager
    
    pm = get_provider_manager()
    providers = pm.get_providers()
    
    configured_providers = []
    
    for provider in providers:
        provider_type = provider.get("type", "")
        provider_name = provider.get("name", "")
        provider_id = provider.get("id", "")
        has_api_key = provider.get("has_api_key", False)
        
        # Vérifier si le provider est utilisable
        if provider_type in ("gemini", "openai", "anthropic") and not has_api_key:
            continue  # Skip providers sans API key
        
        if provider_type in ("ollama", "lmstudio") and not provider.get("url"):
            continue  # Skip providers sans URL
        
        configured_providers.append({
            "id": provider_id,
            "name": provider_name,
            "type": provider_type
        })
    
    return jsonify({"providers": configured_providers})


@api_chat_bp.route("/rag/ocr-models", methods=["GET"])
def get_ocr_models():
    """
    List available models for a specific provider.
    Query param: provider (format: "provider_type:provider_id")
    """
    from ...services.provider_manager import get_provider_manager
    from ...services.llm_clients import get_client_for_provider
    
    provider_key = request.args.get("provider", "")
    
    if not provider_key or ":" not in provider_key:
        return jsonify({"models": [], "error": "Invalid provider format"})
    
    provider_type, provider_id = provider_key.split(":", 1)
    
    # Récupérer le provider complet depuis ProviderManager
    pm = get_provider_manager()
    provider = pm.get_provider(provider_id, include_api_key=True)
    
    if not provider:
        return jsonify({"models": [], "error": "Provider not found"})
    
    # Vision patterns pour identifier les modèles vision
    vision_patterns = [
        "llava", "minicpm-v", "bakllava", "moondream", 
        "cogvlm", "internvl", "-vl", "-vision", "qwen-vl", 
        "qwen2-vl", "qwen3-vl", "4o", "gpt-4-turbo",
        "claude-3", "gemini"
    ]
    
    models = []
    
    try:
        # Passer le dict provider complet à get_client_for_provider
        client = get_client_for_provider(provider)
        models_list = client.list_models() if hasattr(client, 'list_models') else []
        
        for model in models_list:
            model_id = model.get("id", model.get("name", ""))
            model_name = model.get("name", model_id)
            
            # Vérifier si c'est un modèle vision
            model_lower = model_id.lower()
            is_vision = any(pattern in model_lower for pattern in vision_patterns)
            
            # Pour Gemini, OpenAI, Anthropic - tous leurs modèles supportent la vision
            if provider_type in ("gemini", "openai", "anthropic"):
                is_vision = True
            
            models.append({
                "id": model_id,
                "name": model_name,
                "is_vision": is_vision
            })
        
        # Trier : modèles vision en premier
        models.sort(key=lambda x: (not x["is_vision"], x["name"]))
        
    except Exception as e:
        current_app.logger.warning(f"Could not list models for {provider_key}: {e}")
    
    return jsonify({"models": models, "provider": provider_key})


@api_chat_bp.route("/rag/config", methods=["GET"])
def get_rag_config():
    """Get RAG configuration including OCR and Qdrant settings"""
    from ...services.embedding_service import get_embedding_model, get_embedding_provider_id, list_embedding_models
    from ...services.rag_config_service import get_rag_settings
    from ...services.provider_manager import get_provider_manager
    
    # Get configured providers for embedding selection
    configured_providers = []
    try:
        mgr = get_provider_manager()
        providers = mgr.get_providers(include_api_key_masked=False)
        for p in providers:
            # Include providers that support embeddings
            provider_type = p.get("type", "")
            if provider_type in ("ollama", "openai", "openai_compatible", "cohere", "huggingface", "groq", "mistral", "deepseek", "cerebras"):
                configured_providers.append({
                    "id": p["id"],
                    "name": p["name"],
                    "type": provider_type
                })
    except Exception as e:
        current_app.logger.warning(f"Could not list providers: {e}")
    
    # Get embedding provider and models
    embedding_provider_id = get_embedding_provider_id()
    available_models = list_embedding_models(embedding_provider_id)
    
    # Get OCR providers availability
    ocr_providers = []
    try:
        from ...services.vision_ocr_service import list_available_providers
        ocr_providers = list_available_providers()
    except Exception as e:
        current_app.logger.warning(f"Could not list OCR providers: {e}")
    
    # Check Qdrant availability
    qdrant_available = False
    qdrant_stats = None
    try:
        from ...services.qdrant_service import is_qdrant_available, get_collection_stats
        qdrant_available = is_qdrant_available()
        if qdrant_available:
            qdrant_stats = get_collection_stats()
    except Exception as e:
        current_app.logger.warning(f"Could not check Qdrant: {e}")
    
    # Get saved settings
    settings = get_rag_settings()
    
    return jsonify({
        "embedding_model": get_embedding_model(),
        "embedding_provider_id": embedding_provider_id,
        "embedding_providers": configured_providers,
        "available_models": available_models,
        "chunk_size": settings.get("chunk_size", current_app.config.get("RAG_CHUNK_SIZE", 500)),
        "chunk_overlap": settings.get("chunk_overlap", current_app.config.get("RAG_CHUNK_OVERLAP", 50)),
        "top_k": settings.get("top_k", current_app.config.get("RAG_TOP_K", 5)),
        # OCR settings
        "ocr_provider": settings.get("ocr_provider", current_app.config.get("RAG_OCR_PROVIDER", "auto")),
        "ocr_model": settings.get("ocr_model", ""),
        "ocr_threshold": settings.get("ocr_threshold", current_app.config.get("RAG_OCR_THRESHOLD", 50)),
        "ocr_providers_available": ocr_providers,
        # Qdrant settings
        "use_qdrant": settings.get("use_qdrant", current_app.config.get("RAG_USE_QDRANT", True)),
        "qdrant_available": qdrant_available,
        "qdrant_stats": qdrant_stats
    })


@api_chat_bp.route("/rag/config", methods=["POST"])
def set_rag_config():
    """Set RAG configuration (embedding, OCR, Qdrant)"""
    from ...services.embedding_service import set_embedding_model, set_embedding_provider_id
    from ...services.rag_config_service import save_rag_settings
    
    data = request.json or {}
    
    # Save embedding provider if provided
    embedding_provider_id = data.get("embedding_provider_id")
    if embedding_provider_id is not None:
        if not set_embedding_provider_id(embedding_provider_id):
            return jsonify({"error": "Failed to save embedding provider. Check Redis connection."}), 500
    
    # Save embedding model if provided
    embedding_model = data.get("embedding_model")
    if embedding_model:
        if not set_embedding_model(embedding_model):
            return jsonify({"error": "Failed to save embedding model. Check Redis connection."}), 500
    
    # Save other settings
    settings = {
        "chunk_size": data.get("chunk_size", 500),
        "chunk_overlap": data.get("chunk_overlap", 50),
        "top_k": data.get("top_k", 5),
        "ocr_provider": data.get("ocr_provider", ""),  # Format: "provider_type:provider_id"
        "ocr_model": data.get("ocr_model", ""),
        "ocr_threshold": data.get("ocr_threshold", 50),
        "use_qdrant": data.get("use_qdrant", True)
    }
    
    if not save_rag_settings(settings):
        return jsonify({"error": "Failed to save RAG settings. Check Redis connection."}), 500
    
    return jsonify({"status": "updated"})


@api_chat_bp.route("/rag/embedding-models", methods=["GET"])
def get_embedding_models():
    """Get embedding models for a specific provider"""
    from ...services.embedding_service import list_embedding_models
    
    provider_id = request.args.get("provider_id")
    models = list_embedding_models(provider_id)
    
    return jsonify({"models": models})


@api_chat_bp.route("/chat/generate", methods=["POST"])
def generate_chat():
    """
    Stream chat response and save to history.
    Expects: session_id, message, model (optional override), images (optional), files (optional)
    Now includes RAG context augmentation.
    """
    data = request.json or {}
    session_id = data.get("session_id")
    message = data.get("message")
    model = data.get("model")
    images = data.get("images", [])  # List of base64 encoded images
    files = data.get("files", [])    # List of file content dicts [{content, filename, type}]
    web_search = data.get("web_search", False)  # Enable web search via SearXNG
    
    if not message and not images and not files:
        return jsonify({"error": "Message, images, or files required"}), 400

    svc = get_history_service()
    
    # If no session_id, create one
    if not session_id:
        if not model:
            return jsonify({"error": "Model required for new session"}), 400
        session_id = svc.create_session(model)
    
    # Get session to verify and get model if needed
    session = svc.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
        
    current_model = model if model else session.get("model")
    session_system_prompt = session.get("system_prompt", "")
    session_model_config = session.get("model_config", {})
    
    # Get default LLM config and merge with session config
    try:
        from ...services.llm_config_service import get_default_system_prompt, get_default_options
        default_system_prompt = get_default_system_prompt()
        default_options = get_default_options()
    except Exception:
        default_system_prompt = ""
        default_options = {}
    
    # Use session system prompt if set, otherwise use default
    system_prompt = session_system_prompt if session_system_prompt else default_system_prompt
    
    # Merge: default options as base, session config overrides
    model_config = {**default_options, **session_model_config}
    
    # Build the full user message content
    full_message_parts = []
    
    # Add file contents if any
    if files:
        for f in files:
            file_content = f.get("content", "")
            filename = f.get("filename", "file")
            full_message_parts.append(f"[File: {filename}]\n```\n{file_content}\n```\n")
    
    # Add the user message
    if message:
        full_message_parts.append(message)
    
    full_message = "\n".join(full_message_parts) if full_message_parts else message or ""
    
    # Track if we have images for display
    has_images = len(images) > 0
    
    # Add user message to history (with image indicator if applicable)
    user_content = full_message
    if has_images:
        user_content = f"[{len(images)} image(s) attached]\n\n{full_message}" if full_message else f"[{len(images)} image(s) attached]"
    
    svc.add_message(session_id, "user", user_content, images=images if images else None)
    
    # Get RAG context if available
    rag_context = ""
    try:
        from ...services.rag_service import get_context_for_query, init_db
        init_db()
        rag_context, sources = get_context_for_query(session_id, message or "")
    except Exception as e:
        current_app.logger.warning(f"RAG context retrieval failed: {e}")
    
    # Get web search context if enabled
    web_context = ""
    web_sources = []
    memory_context = ""
    memory_concepts = []
    
    if web_search and message:
        try:
            from ...services.web_search_service import search_web, format_search_context, get_searxng_url, get_config
            if get_searxng_url():
                web_search_config = get_config()
                results = search_web(message, max_results=web_search_config.get("max_results", 5))
                if results:
                    web_context = format_search_context(results)
                    web_sources = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in results]
                    
                    # Memory Graph: process results and get memory context
                    try:
                        from ...services.memory_graph_service import process_search_results
                        # Utiliser un user_id par défaut (1) pour le moment
                        # TODO: intégrer avec le système d'authentification si nécessaire
                        user_id = 1
                        memory_context, memory_concepts = process_search_results(
                            user_id=user_id,
                            query=message,
                            search_results=web_sources,
                            session_id=session_id
                        )
                    except Exception as mem_err:
                        current_app.logger.warning(f"Memory Graph processing failed: {mem_err}")
                        
        except Exception as e:
            current_app.logger.warning(f"Web search failed: {e}")
    
    # helper for streaming
    def generate():
        try:
            client = get_llm_client()
        except Exception as client_error:
            yield f"data: {json.dumps({'error': f'Erreur client LLM: {str(client_error)}'})}\n\n"
            return
        
        full_response = []
        full_thinking = []
        
        try:
            # Reload session to get updated messages including the one we just added
            updated_session = svc.get_session(session_id)
            
            # Build chat messages
            chat_messages = []
            
            # Add system prompt if defined
            effective_system = system_prompt
            
            # Add memory context if available (from Memory Graph)
            if memory_context:
                effective_system = memory_context + "\n\n" + (effective_system or "")
            
            # Add web search context if available
            if web_context:
                web_instruction = (
                    "Tu as accès aux résultats de recherche web suivants. "
                    "Utilise ces informations pour fournir des réponses à jour et précises. "
                    "Cite tes sources quand c'est pertinent.\n\n"
                )
                effective_system = web_instruction + web_context + "\n\n" + (effective_system or "")
            
            if rag_context:
                # Prepend RAG context to system prompt
                rag_instruction = (
                    "Tu as accès aux documents suivants fournis par l'utilisateur. "
                    "Utilise ces informations pour répondre aux questions de manière précise. "
                    "Si l'information n'est pas dans les documents, dis-le clairement.\n\n"
                )
                effective_system = rag_instruction + rag_context + "\n\n" + (effective_system or "")
            
            if effective_system:
                chat_messages.append({"role": "system", "content": effective_system})
            
            # Add conversation messages (including images from history)
            for m in updated_session["messages"]:
                msg_data = {"role": m["role"], "content": m["content"]}
                # Include images stored in message history for vision models
                if m.get("images"):
                    msg_data["images"] = m["images"]
                chat_messages.append(msg_data)
            
            # Build options from model_config
            options = {}
            if model_config:
                if "temperature" in model_config:
                    options["temperature"] = float(model_config["temperature"])
                if "num_ctx" in model_config:
                    options["num_ctx"] = int(model_config["num_ctx"])
                if "top_p" in model_config:
                    options["top_p"] = float(model_config["top_p"])
                if "top_k" in model_config:
                    options["top_k"] = int(model_config["top_k"])
                if "repeat_penalty" in model_config:
                    options["repeat_penalty"] = float(model_config["repeat_penalty"])
            
            # Use /api/chat stream with images and options
            for chunk in client.chat_stream(
                messages=chat_messages, 
                model=current_model,
                images=images if images else None,
                options=options if options else None
            ):
                msg_node = chunk.get("message", {})
                content = msg_node.get("content", "")
                thinking = msg_node.get("thinking", "")
                
                done = chunk.get("done", False)

                if content:
                    full_response.append(content)
                if thinking:
                    full_thinking.append(thinking)
                    
                # SSE Format: Send thinking and content separately
                # Include web sources on first chunk or when done
                response_data = {
                    'role': 'assistant', 
                    'content': content, 
                    'thinking': thinking, 
                    'done': done, 
                    'session_id': session_id
                }
                # Send web sources and memory concepts with the final message
                if done and web_sources:
                    response_data['web_sources'] = web_sources
                if done and memory_concepts:
                    response_data['memory_concepts'] = memory_concepts
                yield f"data: {json.dumps(response_data)}\n\n"

            # Save full assistant message
            assistant_content = "".join(full_response)
            assistant_thinking = "".join(full_thinking) if full_thinking else None
            
            # Include web sources and memory concepts in extra_data if available
            extra_data = None
            if web_sources or memory_concepts:
                extra_data = {}
                if web_sources:
                    extra_data["web_sources"] = web_sources
                if memory_concepts:
                    extra_data["memory_concepts"] = memory_concepts
            
            svc.add_message(session_id, "assistant", assistant_content, thinking=assistant_thinking, extra_data=extra_data)
            
            # Générer le titre si c'est le premier échange et que l'option est activée
            try:
                session_data = svc.get_session(session_id)
                current_app.logger.info(f"[Title Gen] Session title: {session_data.get('title') if session_data else 'None'}")
                
                if session_data and session_data.get("title") == "New Chat":
                    user_messages = [m for m in session_data.get("messages", []) if m.get("role") == "user"]
                    current_app.logger.info(f"[Title Gen] User messages count: {len(user_messages)}")
                    
                    if len(user_messages) == 1:  # Premier message utilisateur
                        from ...services.llm_config_service import is_auto_title_enabled
                        auto_enabled = is_auto_title_enabled()
                        current_app.logger.info(f"[Title Gen] Auto title enabled: {auto_enabled}")
                        
                        if auto_enabled:
                            first_user_message = user_messages[0].get("content", "")
                            # Nettoyer le message (enlever préfixes d'images/fichiers)
                            clean_message = first_user_message
                            if clean_message.startswith("["):
                                # Enlever les préfixes comme "[2 image(s) attached]"
                                import re
                                clean_message = re.sub(r'^\[\d+ image\(s\) attached\]\s*', '', clean_message, flags=re.IGNORECASE)
                                clean_message = re.sub(r'^\[File: [^\]]+\]\s*', '', clean_message, flags=re.MULTILINE)
                            clean_message = clean_message.strip()
                            
                            current_app.logger.info(f"[Title Gen] Generating title for: {clean_message[:50]}...")
                            new_title = generate_title(clean_message, current_model)
                            current_app.logger.info(f"[Title Gen] Generated title: {new_title}")
                            
                            svc.update_session_settings(session_id, title=new_title)
                            # Envoyer le nouveau titre au client
                            yield f"data: {json.dumps({'title_update': new_title, 'session_id': session_id})}\n\n"
            except Exception as e:
                current_app.logger.error(f"[Title Gen] Error generating title: {e}", exc_info=True)
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# ============== Multi-LLM Debate Endpoints ==============

@api_chat_bp.route("/chat/debate/providers", methods=["GET"])
def list_debate_providers():
    """
    Liste les providers disponibles pour le mode débat.
    Retourne id, name, type, color, default_model pour chaque provider.
    """
    from ...services.debate_service import get_debate_service
    
    try:
        service = get_debate_service()
        providers = service.get_available_providers()
        return jsonify({"providers": providers})
    except Exception as e:
        current_app.logger.error(f"Error listing debate providers: {e}")
        return jsonify({"providers": [], "error": str(e)}), 500


@api_chat_bp.route("/chat/debate", methods=["POST"])
def generate_debate():
    """
    Stream des réponses multi-LLM en mode débat.
    
    Body JSON:
    {
        "session_id": "...",           # Session existante ou null pour créer
        "message": "...",              # Message de l'utilisateur
        "participants": [              # Liste des participants
            {
                "provider_id": "...",
                "model": "...",
                "name": "...",         # Optionnel, display name
                "system_prompt": "..." # Optionnel, persona
            }
        ],
        "mode": "parallel" | "sequential",  # Mode de débat
        "rounds": 1                    # Nombre de tours (mode séquentiel)
    }
    
    SSE Response format:
    data: {"participant_id": "...", "name": "...", "color": "...", "content": "...", "done": false}
    """
    from ...services.debate_service import get_debate_service, Participant
    
    data = request.json or {}
    session_id = data.get("session_id")
    message = data.get("message", "").strip()
    participants_data = data.get("participants", [])
    mode = data.get("mode", "parallel")
    rounds = data.get("rounds", 1)
    global_system_prompt = data.get("system_prompt", "")  # Prompt global pour tous les participants
    
    # Validation
    if not message:
        return jsonify({"error": "Message required"}), 400
    
    if not participants_data or len(participants_data) < 2:
        return jsonify({"error": "At least 2 participants required"}), 400
    
    if len(participants_data) > 4:
        return jsonify({"error": "Maximum 4 participants allowed"}), 400
    
    svc = get_history_service()
    debate_service = get_debate_service()
    
    # Créer la session si nécessaire
    if not session_id:
        # Créer avec le premier modèle comme référence
        first_model = participants_data[0].get("model", "debate")
        session_id = svc.create_session(first_model, "Debate: " + message[:30])
    
    # Vérifier que la session existe
    session = svc.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    # Construire les participants
    participants = []
    for i, p_data in enumerate(participants_data):
        provider_id = p_data.get("provider_id")
        if not provider_id:
            return jsonify({"error": f"provider_id required for participant {i}"}), 400
        
        model = p_data.get("model")
        if not model:
            return jsonify({"error": f"model required for participant {i}"}), 400
        
        # Récupérer les infos du provider pour la couleur
        provider = debate_service.provider_manager.get_provider(provider_id)
        if not provider:
            return jsonify({"error": f"Provider {provider_id} not found"}), 404
        
        color = debate_service.get_provider_color(provider.get("type", ""))
        
        participant = Participant(
            id=str(uuid.uuid4()),
            provider_id=provider_id,
            model=model,
            name=p_data.get("name", f"{provider.get('name', 'LLM')} ({model})"),
            color=color,
            system_prompt=p_data.get("system_prompt", "")
        )
        
        # Utiliser le system_prompt global s'il est fourni, sinon construire un défaut
        if global_system_prompt:
            participant.system_prompt = global_system_prompt
        else:
            other_participants = [Participant.from_dict(pd) for pd in participants_data if pd != p_data]
            participant.system_prompt = debate_service.build_debate_system_prompt(
                participant, 
                other_participants,
                message
            )
        
        participants.append(participant)
    
    # Sauvegarder les participants dans les métadonnées de session
    participants_info = [
        {"id": p.id, "name": p.name, "model": p.model, "provider_id": p.provider_id, "color": p.color}
        for p in participants
    ]
    svc.update_session_settings(session_id, model_config={"debate_participants": participants_info, "debate_mode": mode})
    
    # Ajouter le message utilisateur à l'historique
    svc.add_message(session_id, "user", message)
    
    # Récupérer l'historique pour le contexte
    session_messages = session.get("messages", [])
    context_messages = [{"role": m["role"], "content": m["content"]} for m in session_messages]
    
    def generate():
        import time
        
        try:
            # Envoyer l'ID de session au début
            yield f"data: {json.dumps({'session_id': session_id, 'start': True})}\n\n"
            
            # Stocker les réponses complètes par participant
            responses = {p.id: {"name": p.name, "color": p.color, "content": ""} for p in participants}
            
            if mode == "parallel":
                # Mode parallèle : tous les LLM répondent en même temps
                for chunk in debate_service.parallel_generate(
                    participants=participants,
                    messages=context_messages + [{"role": "user", "content": message}]
                ):
                    participant_id = chunk.get("participant_id")
                    if participant_id and chunk.get("content"):
                        responses[participant_id]["content"] += chunk.get("content", "")
                    
                    yield f"data: {json.dumps(chunk)}\n\n"
                    
            else:  # mode == "sequential"
                # Mode séquentiel : chaque LLM réagit aux précédents
                for chunk in debate_service.sequential_generate(
                    participants=participants,
                    user_message=message,
                    conversation_history=context_messages,
                    rounds=rounds
                ):
                    participant_id = chunk.get("participant_id")
                    if participant_id and chunk.get("content"):
                        responses[participant_id]["content"] += chunk.get("content", "")
                    
                    yield f"data: {json.dumps(chunk)}\n\n"
            
            # Sauvegarder les réponses dans l'historique
            for participant_id, resp_data in responses.items():
                if resp_data["content"]:
                    participant = next((p for p in participants if p.id == participant_id), None)
                    if participant:
                        # Ajouter un préfixe pour identifier le participant
                        formatted_content = f"[{resp_data['name']}]: {resp_data['content']}"
                        svc.add_message(
                            session_id, 
                            "assistant", 
                            formatted_content,
                            extra_data={
                                "participant_id": participant_id,
                                "participant_name": resp_data["name"],
                                "participant_color": resp_data["color"]
                            }
                        )
            
            # Signal de fin
            yield f"data: {json.dumps({'complete': True, 'session_id': session_id})}\n\n"
            
        except Exception as e:
            current_app.logger.error(f"Debate generation error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@api_chat_bp.route("/chat/debate/session/<session_id>/participants", methods=["GET"])
def get_debate_participants(session_id):
    """Récupère les participants d'une session de débat."""
    svc = get_history_service()
    session = svc.get_session(session_id)
    
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    # Extraire les participants des messages
    participants = []
    seen_ids = set()
    
    for msg in session.get("messages", []):
        extra = msg.get("extra_data", {})
        participant_id = extra.get("participant_id")
        if participant_id and participant_id not in seen_ids:
            seen_ids.add(participant_id)
            participants.append({
                "id": participant_id,
                "name": extra.get("participant_name", "Unknown"),
                "color": extra.get("participant_color", "zinc")
            })
    
    return jsonify({"participants": participants})


@api_chat_bp.route("/chat/debate/defaults", methods=["GET"])
def get_debate_defaults():
    """Get default participants for debate mode."""
    svc = get_debate_service()
    defaults = svc.get_debate_defaults()
    return jsonify(defaults)


@api_chat_bp.route("/chat/debate/defaults", methods=["POST"])
def save_debate_defaults():
    """Save current participants as default."""
    data = request.json or []
    if not isinstance(data, list):
        return jsonify({"error": "Invalid data format, expected list"}), 400
        
    svc = get_debate_service()
    if svc.save_debate_defaults(data):
        return jsonify({"status": "saved"})
    return jsonify({"error": "Failed to save"}), 500


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY GRAPH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@api_chat_bp.route("/chat/memory/concept", methods=["DELETE"])
def delete_memory_concept():
    """
    Supprime un concept du graphe mémoire et met à jour le message en base.
    Body: {
        "concept": "nom_du_concept",
        "session_id": "uuid (optionnel)",
        "message_index": int (optionnel),
        "remaining_concepts": [...] (optionnel) - concepts restants après suppression
    }
    """
    data = request.json or {}
    concept = data.get("concept", "").strip()
    session_id = data.get("session_id")
    message_index = data.get("message_index")
    remaining_concepts = data.get("remaining_concepts")
    
    current_app.logger.info(f"[Memory] DELETE request - concept: '{concept}', session: {session_id}, msg_idx: {message_index}")
    
    if not concept:
        return jsonify({"error": "Concept name required"}), 400
    
    try:
        from ...services.memory_graph_service import delete_node_by_concept
        from ...services.chat_history_pg import ChatHistoryService
        
        # TODO: utiliser l'ID de l'utilisateur connecté quand l'auth est en place
        user_id = 1
        
        # 1. Supprimer du graphe mémoire
        result = delete_node_by_concept(user_id, concept)
        current_app.logger.info(f"[Memory] delete_node_by_concept('{concept}') returned: {result}")
        
        # 2. Mettre à jour extra_data du message si les infos sont fournies
        if session_id and message_index is not None and remaining_concepts is not None:
            try:
                history_service = ChatHistoryService()
                # Récupérer le message actuel pour conserver les autres données extra
                session = history_service.get_session(session_id)
                if session and 'messages' in session and message_index < len(session['messages']):
                    msg = session['messages'][message_index]
                    extra = msg.get('extra_data') or {}
                    extra['memory_concepts'] = remaining_concepts
                    history_service.update_message_extra_data(session_id, message_index, extra)
                    current_app.logger.info(f"[Memory] Updated extra_data for message {message_index} in session {session_id}")
            except Exception as e:
                current_app.logger.error(f"[Memory] Failed to update message extra_data: {e}")
        
        # Retourner succès même si le concept n'existait pas en base
        # (car il peut avoir été généré par le fallback heuristique)
        return jsonify({"status": "deleted" if result else "not_found_in_graph", "concept": concept})
            
    except Exception as e:
        current_app.logger.error(f"Error deleting concept: {e}")
        return jsonify({"error": str(e)}), 500

