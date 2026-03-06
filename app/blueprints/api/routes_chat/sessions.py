import os
from flask import jsonify, request, current_app
from . import api_chat_bp, get_history_service, MAX_FILE_SIZE, ALLOWED_TEXT_EXTENSIONS


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
    try:
        from ....services.rag_service import delete_session_documents
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

    try:
        from ....services.rag_service import delete_session_documents
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
    sessions = svc.list_sessions()

    try:
        from ....services.rag_service import delete_session_documents
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
    """Handle file upload, extract text content."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    if size > MAX_FILE_SIZE:
        return jsonify({"error": f"File too large. Maximum size is {MAX_FILE_SIZE // 1024 // 1024} MB"}), 400

    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_TEXT_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_TEXT_EXTENSIONS))}"}), 400

    try:
        content = file.read().decode('utf-8', errors='replace')
        return jsonify({
            "content": content,
            "filename": filename,
            "type": ext[1:] if ext else "txt",
            "size": size
        })
    except Exception as e:
        return jsonify({"error": f"Failed to read file: {str(e)}"}), 500
