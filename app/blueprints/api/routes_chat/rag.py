import os
import uuid
from flask import jsonify, request, current_app
from . import api_chat_bp, MAX_PDF_SIZE


@api_chat_bp.route("/chat/upload-pdf", methods=["POST"])
def upload_pdf():
    """Upload a PDF file and index it for RAG."""
    from ....services.embedding_service import get_embedding_model
    from ....services.rag_service import store_document, init_db

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

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    if size > MAX_PDF_SIZE:
        return jsonify({"error": f"File too large. Maximum size is {MAX_PDF_SIZE // 1024 // 1024} MB"}), 400

    embedding_model = get_embedding_model()
    if not embedding_model:
        return jsonify({"error": "No embedding model configured. Please configure one in Settings > RAG."}), 400

    try:
        init_db()
        uploads_dir = current_app.config.get("RAG_UPLOADS_DIR", "/app/rag_uploads")
        os.makedirs(uploads_dir, exist_ok=True)

        file_id = str(uuid.uuid4())
        file_path = os.path.join(uploads_dir, f"{file_id}.pdf")
        file.save(file_path)

        doc_id = store_document(
            session_id=session_id,
            filename=filename,
            file_path=file_path,
            chunks=None,
            embeddings=None,
            embedding_model=embedding_model,
            embedding_dimensions=None,
            status='pending'
        )

        try:
            if hasattr(current_app, 'rq') and current_app.rq:
                from ....tasks.rag_tasks import process_document_background
                job = current_app.rq.enqueue(
                    process_document_background,
                    args=(doc_id, session_id, filename, file_path),
                    job_timeout=current_app.config.get("RQ_DEFAULT_JOB_TIMEOUT", 3600)
                )
                current_app.logger.info(f"Enqueued PDF processing job {job.id} for doc {doc_id}")
            else:
                current_app.logger.warning("RQ not available, falling back to synchronous processing")
                from ....tasks.rag_tasks import process_document_background
                process_document_background(doc_id, session_id, filename, file_path)
        except Exception as e:
            current_app.logger.error(f"Failed to enqueue task: {e}")
            return jsonify({"error": "Failed to start processing"}), 500

        return jsonify({"message": "File uploaded and processing started", "document_id": doc_id, "status": "pending"})
    except Exception as e:
        current_app.logger.error(f"Error uploading PDF: {e}")
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500


@api_chat_bp.route("/chat/sessions/<session_id>/documents", methods=["GET"])
def list_session_documents(session_id):
    """List all RAG documents attached to a session"""
    from ....services.rag_service import list_documents, init_db
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
    from ....services.rag_service import get_document_chunks, get_document_stats
    chunks = get_document_chunks(document_id)
    stats = get_document_stats(document_id)
    return jsonify({"chunks": chunks, "stats": stats})


@api_chat_bp.route("/rag/chunks/<chunk_id>", methods=["DELETE"])
def delete_chunk_route(chunk_id):
    """Delete a specific chunk"""
    from ....services.rag_service import delete_chunk as svc_delete_chunk
    if svc_delete_chunk(chunk_id):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Failed to delete chunk"}), 500


@api_chat_bp.route("/rag/documents/<document_id>/search", methods=["POST"])
def search_in_document(document_id):
    """Search chunks within a specific document"""
    from ....services.rag_service import search_similar, get_document_metadata
    from ....services.embedding_service import generate_embedding

    data = request.json or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query required"}), 400

    doc_meta = get_document_metadata(document_id)
    if not doc_meta:
        return jsonify({"error": "Document not found"}), 404

    session_id = doc_meta["session_id"]
    try:
        query_embedding = generate_embedding(query)
        if not query_embedding:
            return jsonify({"error": "Failed to generate embedding"}), 500
        chunks = search_similar(session_id=session_id, query_embedding=query_embedding, top_k=20, document_id=document_id)
        return jsonify({"results": chunks})
    except Exception as e:
        current_app.logger.error(f"Error searching document chunks: {e}")
        return jsonify({"error": str(e)}), 500


@api_chat_bp.route("/chat/documents/<document_id>", methods=["DELETE"])
def delete_document(document_id):
    """Delete a RAG document"""
    from ....services.rag_service import delete_document as rag_delete_document
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
    """List configured LLM providers that can be used for OCR."""
    from ....services.provider_manager import get_provider_manager
    pm = get_provider_manager()
    providers = pm.get_providers()
    configured_providers = []
    for provider in providers:
        provider_type = provider.get("type", "")
        if provider_type in ("gemini", "openai", "anthropic") and not provider.get("has_api_key", False):
            continue
        if provider_type in ("ollama", "lmstudio") and not provider.get("url"):
            continue
        configured_providers.append({"id": provider.get("id", ""), "name": provider.get("name", ""), "type": provider_type})
    return jsonify({"providers": configured_providers})


@api_chat_bp.route("/rag/ocr-models", methods=["GET"])
def get_ocr_models():
    """List available models for a specific provider."""
    from ....services.provider_manager import get_provider_manager
    from ....services.llm_clients import get_client_for_provider

    provider_key = request.args.get("provider", "")
    if not provider_key or ":" not in provider_key:
        return jsonify({"models": [], "error": "Invalid provider format"})

    provider_type, provider_id = provider_key.split(":", 1)
    pm = get_provider_manager()
    provider = pm.get_provider(provider_id, include_api_key=True)
    if not provider:
        return jsonify({"models": [], "error": "Provider not found"})

    vision_patterns = [
        "llava", "minicpm-v", "bakllava", "moondream",
        "cogvlm", "internvl", "-vl", "-vision", "qwen-vl",
        "qwen2-vl", "qwen3-vl", "4o", "gpt-4-turbo",
        "claude-3", "gemini"
    ]

    models = []
    try:
        client = get_client_for_provider(provider)
        models_list = client.list_models() if hasattr(client, 'list_models') else []
        for model in models_list:
            model_id = model.get("id", model.get("name", ""))
            model_name = model.get("name", model_id)
            model_lower = model_id.lower()
            is_vision = any(pattern in model_lower for pattern in vision_patterns)
            if provider_type in ("gemini", "openai", "anthropic"):
                is_vision = True
            models.append({"id": model_id, "name": model_name, "is_vision": is_vision})
        models.sort(key=lambda x: (not x["is_vision"], x["name"]))
    except Exception as e:
        current_app.logger.warning(f"Could not list models for {provider_key}: {e}")

    return jsonify({"models": models, "provider": provider_key})


@api_chat_bp.route("/rag/config", methods=["GET"])
def get_rag_config():
    """Get RAG configuration including OCR and Qdrant settings"""
    from ....services.embedding_service import get_embedding_model, get_embedding_provider_id, list_embedding_models
    from ....services.rag_config_service import get_rag_settings
    from ....services.provider_manager import get_provider_manager

    configured_providers = []
    try:
        mgr = get_provider_manager()
        providers = mgr.get_providers(include_api_key_masked=False)
        for p in providers:
            provider_type = p.get("type", "")
            if provider_type in ("ollama", "openai", "openai_compatible", "cohere", "huggingface", "groq", "mistral", "deepseek", "cerebras"):
                configured_providers.append({"id": p["id"], "name": p["name"], "type": provider_type})
    except Exception as e:
        current_app.logger.warning(f"Could not list providers: {e}")

    embedding_provider_id = get_embedding_provider_id()
    available_models = list_embedding_models(embedding_provider_id)

    ocr_providers = []
    try:
        from ....services.vision_ocr_service import list_available_providers
        ocr_providers = list_available_providers()
    except Exception as e:
        current_app.logger.warning(f"Could not list OCR providers: {e}")

    qdrant_available = False
    qdrant_stats = None
    try:
        from ....services.qdrant_service import is_qdrant_available, get_collection_stats
        qdrant_available = is_qdrant_available()
        if qdrant_available:
            qdrant_stats = get_collection_stats()
    except Exception as e:
        current_app.logger.warning(f"Could not check Qdrant: {e}")

    settings = get_rag_settings()

    return jsonify({
        "embedding_model": get_embedding_model(),
        "embedding_provider_id": embedding_provider_id,
        "embedding_providers": configured_providers,
        "available_models": available_models,
        "chunk_size": settings.get("chunk_size", current_app.config.get("RAG_CHUNK_SIZE", 500)),
        "chunk_overlap": settings.get("chunk_overlap", current_app.config.get("RAG_CHUNK_OVERLAP", 50)),
        "top_k": settings.get("top_k", current_app.config.get("RAG_TOP_K", 5)),
        "ocr_provider": settings.get("ocr_provider", current_app.config.get("RAG_OCR_PROVIDER", "auto")),
        "ocr_model": settings.get("ocr_model", ""),
        "ocr_threshold": settings.get("ocr_threshold", current_app.config.get("RAG_OCR_THRESHOLD", 50)),
        "ocr_providers_available": ocr_providers,
        "use_qdrant": settings.get("use_qdrant", current_app.config.get("RAG_USE_QDRANT", True)),
        "qdrant_available": qdrant_available,
        "qdrant_stats": qdrant_stats
    })


@api_chat_bp.route("/rag/config", methods=["POST"])
def set_rag_config():
    """Set RAG configuration (embedding, OCR, Qdrant)"""
    from ....services.embedding_service import set_embedding_model, set_embedding_provider_id
    from ....services.rag_config_service import save_rag_settings

    data = request.json or {}

    embedding_provider_id = data.get("embedding_provider_id")
    if embedding_provider_id is not None:
        if not set_embedding_provider_id(embedding_provider_id):
            return jsonify({"error": "Failed to save embedding provider. Check Redis connection."}), 500

    embedding_model = data.get("embedding_model")
    if embedding_model:
        if not set_embedding_model(embedding_model):
            return jsonify({"error": "Failed to save embedding model. Check Redis connection."}), 500

    settings = {
        "chunk_size": data.get("chunk_size", 500),
        "chunk_overlap": data.get("chunk_overlap", 50),
        "top_k": data.get("top_k", 5),
        "ocr_provider": data.get("ocr_provider", ""),
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
    from ....services.embedding_service import list_embedding_models
    provider_id = request.args.get("provider_id")
    models = list_embedding_models(provider_id)
    return jsonify({"models": models})
