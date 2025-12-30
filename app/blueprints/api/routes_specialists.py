"""
Routes API pour la gestion des Spécialistes (assistants IA personnalisés)
"""

import json
from flask import Blueprint, jsonify, request, Response, stream_with_context, current_app
from flask_login import login_required, current_user

from ...services import specialist_service as svc
from ...services.llm_clients import get_active_client
from ...services.provider_manager import ProviderManager


specialists_bp = Blueprint("specialists", __name__)


def get_user_id() -> str:
    """Récupère l'ID de l'utilisateur courant."""
    return str(current_user.id) if current_user.is_authenticated else "anonymous"


# ============== CRUD Spécialistes ==============

@specialists_bp.route("/specialists", methods=["GET"])
@login_required
def list_specialists():
    """Liste les spécialistes de l'utilisateur."""
    try:
        specialists = svc.list_specialists(get_user_id())
        return jsonify({"specialists": specialists})
    except Exception as e:
        current_app.logger.error(f"Error listing specialists: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists", methods=["POST"])
@login_required
def create_specialist():
    """Crée un nouveau spécialiste."""
    data = request.get_json(silent=True) or {}
    
    name = data.get("name")
    system_prompt = data.get("system_prompt")
    
    if not name or not system_prompt:
        return jsonify({"error": "name et system_prompt sont requis"}), 400
    
    try:
        specialist = svc.create_specialist(
            user_id=get_user_id(),
            name=name,
            system_prompt=system_prompt,
            description=data.get("description"),
            model=data.get("model"),
            avatar_url=data.get("avatar_url"),
            color=data.get("color", "#6366f1"),
            icon=data.get("icon", "computer"),
            provider_id=data.get("provider_id")
        )
        return jsonify(specialist), 201
    except Exception as e:
        current_app.logger.error(f"Error creating specialist: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>", methods=["GET"])
@login_required
def get_specialist(specialist_id: str):
    """Récupère un spécialiste avec ses connaissances et outils."""
    try:
        specialist = svc.get_specialist(specialist_id, get_user_id())
        if not specialist:
            return jsonify({"error": "Spécialiste non trouvé"}), 404
        return jsonify(specialist)
    except Exception as e:
        current_app.logger.error(f"Error getting specialist: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>", methods=["PUT"])
@login_required
def update_specialist(specialist_id: str):
    """Met à jour un spécialiste."""
    data = request.get_json(silent=True) or {}
    
    try:
        specialist = svc.update_specialist(
            specialist_id=specialist_id,
            user_id=get_user_id(),
            name=data.get("name"),
            description=data.get("description"),
            system_prompt=data.get("system_prompt"),
            model=data.get("model"),
            avatar_url=data.get("avatar_url"),
            color=data.get("color"),
            icon=data.get("icon"),
            provider_id=data.get("provider_id")
        )
        
        if not specialist:
            return jsonify({"error": "Spécialiste non trouvé"}), 404
        
        return jsonify(specialist)
    except Exception as e:
        current_app.logger.error(f"Error updating specialist: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>", methods=["DELETE"])
@login_required
def delete_specialist(specialist_id: str):
    """Supprime un spécialiste et toutes ses données."""
    try:
        deleted = svc.delete_specialist(specialist_id, get_user_id())
        if not deleted:
            return jsonify({"error": "Spécialiste non trouvé"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        current_app.logger.error(f"Error deleting specialist: {e}")
        return jsonify({"error": str(e)}), 500


# ============== Gestion des Connaissances ==============

@specialists_bp.route("/specialists/<specialist_id>/knowledge", methods=["GET"])
@login_required
def list_knowledge(specialist_id: str):
    """Liste les connaissances d'un spécialiste."""
    # Vérifier que le spécialiste appartient à l'utilisateur
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    try:
        knowledge = svc.list_knowledge(specialist_id)
        return jsonify({"knowledge": knowledge})
    except Exception as e:
        current_app.logger.error(f"Error listing knowledge: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/knowledge/text", methods=["POST"])
@login_required
def add_knowledge_text(specialist_id: str):
    """Ajoute une connaissance textuelle."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    content = data.get("content")
    
    if not name or not content:
        return jsonify({"error": "name et content sont requis"}), 400
    
    try:
        knowledge = svc.add_knowledge_text(
            specialist_id=specialist_id,
            name=name,
            content=content,
            knowledge_type="text"
        )
        return jsonify(knowledge), 201
    except Exception as e:
        current_app.logger.error(f"Error adding text knowledge: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/knowledge/upload", methods=["POST"])
@login_required
def upload_knowledge_file(specialist_id: str):
    """Upload un fichier comme connaissance (PDF, texte, image)."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400
    
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Nom de fichier vide"}), 400
    
    try:
        file_bytes = file.read()
        knowledge = svc.add_knowledge_file(
            specialist_id=specialist_id,
            filename=file.filename,
            file_bytes=file_bytes,
            file_type=file.content_type or ""
        )
        return jsonify(knowledge), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error uploading file: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/knowledge/web", methods=["POST"])
@login_required
def add_knowledge_web(specialist_id: str):
    """Ajoute une URL comme connaissance."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    
    if not url:
        return jsonify({"error": "URL requise"}), 400
    
    try:
        knowledge = svc.add_knowledge_web(specialist_id, url)
        return jsonify(knowledge), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error adding web knowledge: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/knowledge/<knowledge_id>", methods=["DELETE"])
@login_required
def delete_knowledge(specialist_id: str, knowledge_id: str):
    """Supprime une connaissance."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    try:
        deleted = svc.delete_knowledge(knowledge_id, specialist_id)
        if not deleted:
            return jsonify({"error": "Connaissance non trouvée"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        current_app.logger.error(f"Error deleting knowledge: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/knowledge/<knowledge_id>/chunks", methods=["GET"])
@login_required
def get_knowledge_chunks(specialist_id: str, knowledge_id: str):
    """Récupère les chunks d'une connaissance."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    try:
        data = svc.get_knowledge_chunks(knowledge_id, specialist_id)
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Error getting knowledge chunks: {e}")
        return jsonify({"error": str(e)}), 500


# ============== Gestion des Outils ==============

@specialists_bp.route("/specialists/<specialist_id>/tools", methods=["GET"])
@login_required
def list_tools(specialist_id: str):
    """Liste les outils d'un spécialiste."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    try:
        tools = svc.list_tools(specialist_id)
        return jsonify({"tools": tools})
    except Exception as e:
        current_app.logger.error(f"Error listing tools: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/tools", methods=["POST"])
@login_required
def add_tool(specialist_id: str):
    """Ajoute un outil au spécialiste."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    tool_type = data.get("type")
    config = data.get("config", {})
    
    if not name or not tool_type:
        return jsonify({"error": "name et type sont requis"}), 400
    
    try:
        tool = svc.add_tool(
            specialist_id=specialist_id,
            name=name,
            tool_type=tool_type,
            config=config
        )
        return jsonify(tool), 201
    except Exception as e:
        current_app.logger.error(f"Error adding tool: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/tools/<tool_id>", methods=["PUT"])
@login_required
def update_tool(specialist_id: str, tool_id: str):
    """Met à jour un outil."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    data = request.get_json(silent=True) or {}
    
    try:
        tool = svc.update_tool(
            tool_id=tool_id,
            specialist_id=specialist_id,
            name=data.get("name"),
            config=data.get("config"),
            enabled=data.get("enabled")
        )
        if not tool:
            return jsonify({"error": "Outil non trouvé"}), 404
        return jsonify(tool)
    except Exception as e:
        current_app.logger.error(f"Error updating tool: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/tools/<tool_id>", methods=["DELETE"])
@login_required
def delete_tool(specialist_id: str, tool_id: str):
    """Supprime un outil."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    try:
        deleted = svc.delete_tool(tool_id, specialist_id)
        if not deleted:
            return jsonify({"error": "Outil non trouvé"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        current_app.logger.error(f"Error deleting tool: {e}")
        return jsonify({"error": str(e)}), 500


# ============== Sessions de Chat ==============

@specialists_bp.route("/specialists/<specialist_id>/sessions", methods=["GET"])
@login_required
def list_sessions(specialist_id: str):
    """Liste les sessions de chat d'un spécialiste."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    try:
        sessions = svc.list_sessions(specialist_id, get_user_id())
        return jsonify({"sessions": sessions})
    except Exception as e:
        current_app.logger.error(f"Error listing sessions: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/sessions", methods=["POST"])
@login_required
def create_session(specialist_id: str):
    """Crée une nouvelle session de chat."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    data = request.get_json(silent=True) or {}
    
    try:
        session = svc.create_session(specialist_id, get_user_id(), data.get("title"))
        return jsonify(session), 201
    except Exception as e:
        current_app.logger.error(f"Error creating session: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/sessions/<session_id>/messages", methods=["GET"])
@login_required
def get_session_messages(specialist_id: str, session_id: str):
    """Récupère les messages d'une session."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    try:
        messages = svc.get_session_messages(session_id)
        return jsonify({"messages": messages})
    except Exception as e:
        current_app.logger.error(f"Error getting messages: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/sessions/<session_id>", methods=["DELETE"])
@login_required
def delete_session(specialist_id: str, session_id: str):
    """Supprime une session."""
    try:
        deleted = svc.delete_session(session_id, specialist_id, get_user_id())
        if not deleted:
            return jsonify({"error": "Session non trouvée"}), 404
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/sessions/bulk", methods=["DELETE"])
@login_required
def delete_sessions_bulk(specialist_id: str):
    """Supprime plusieurs sessions."""
    data = request.get_json(silent=True) or {}
    session_ids = data.get("session_ids", [])
    
    if not session_ids:
        return jsonify({"error": "session_ids requis"}), 400
    
    try:
        deleted_count = svc.delete_sessions(session_ids, specialist_id, get_user_id())
        return jsonify({"status": "deleted", "deleted_count": deleted_count})
    except Exception as e:
        current_app.logger.error(f"Error deleting sessions bulk: {e}")
        return jsonify({"error": str(e)}), 500


@specialists_bp.route("/specialists/<specialist_id>/sessions/all", methods=["DELETE"])
@login_required
def delete_all_sessions(specialist_id: str):
    """Supprime toutes les sessions d'un spécialiste."""
    try:
        deleted_count = svc.delete_all_sessions(specialist_id, get_user_id())
        return jsonify({"status": "deleted", "deleted_count": deleted_count})
    except Exception as e:
        current_app.logger.error(f"Error deleting all sessions: {e}")
        return jsonify({"error": str(e)}), 500


# ============== Chat avec Spécialiste ==============

@specialists_bp.route("/specialists/<specialist_id>/chat", methods=["POST"])
@login_required
def chat_with_specialist(specialist_id: str):
    """
    Chat avec un spécialiste (streaming SSE).
    
    Body JSON:
    {
        "message": "...",
        "session_id": "..." (optionnel, crée une nouvelle session si absent)
    }
    """
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    session_id = data.get("session_id")
    
    if not message:
        return jsonify({"error": "Message requis"}), 400
    
    # Créer ou récupérer la session
    if not session_id:
        # Titre basé sur le message (tronqué)
        title = message[:50] + "..." if len(message) > 50 else message
        session = svc.create_session(specialist_id, get_user_id(), title=title)
        session_id = session["id"]
    
    def generate():
        try:
            # Sauvegarder le message utilisateur
            svc.add_message(session_id, "user", message)
            
            # Récupérer le contexte RAG
            context, sources = svc.get_context_for_query(specialist_id, message)
            
            # Construire le prompt système enrichi
            system_prompt = specialist["system_prompt"]
            if context:
                system_prompt += f"\n\n{context}"
            
            # Récupérer les messages de l'historique
            history = svc.get_session_messages(session_id)
            
            # Construire la liste des messages avec system prompt en premier
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            for msg in history[:-1]:  # Exclure le message qu'on vient d'ajouter
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            messages.append({"role": "user", "content": message})
            
            # Obtenir le client LLM
            try:
                # Si le spécialiste a un provider défini, l'utiliser prioritairement
                provider_id = specialist.get("provider_id")
                client = None
                
                if provider_id:
                    try:
                        data_path = current_app.root_path + "/data/providers.json"
                        mgr = ProviderManager(data_path)
                        provider = mgr.get_provider(provider_id, include_api_key=True)
                        if provider:
                            from ...services.llm_clients import get_client_for_provider
                            client = get_client_for_provider(provider)
                    except Exception as e:
                        current_app.logger.warning(f"Failed to get client for provider {provider_id}: {e}")
                
                # Fallback sur le client actif
                if not client:
                    client = get_active_client()
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return
            
            # Déterminer le modèle
            model = specialist.get("model")
            if not model:
                # Utiliser le modèle par défaut du provider
                data_path = current_app.root_path + "/data/providers.json"
                mgr = ProviderManager(data_path)
                active = mgr.get_active_provider()
                model = active.get("default_model") if active else None
            
            if not model:
                yield f"data: {json.dumps({'error': 'Aucun modèle configuré'})}\n\n"
                return
            
            # Envoyer les infos de session
            yield f"data: {json.dumps({'session_id': session_id, 'sources': sources})}\n\n"
            
            # Streamer la réponse
            full_response = ""
            
            for chunk in client.chat_stream(
                model=model,
                messages=messages
            ):
                # Gérer les différents formats de réponse des clients
                if "message" in chunk:
                    content = chunk["message"].get("content", "")
                else:
                    content = chunk.get("content", "")
                if content:
                    full_response += content
                    yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"
            
            # Sauvegarder la réponse complète
            svc.add_message(session_id, "assistant", full_response, sources)
            
            yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
            
        except Exception as e:
            current_app.logger.error(f"Error in specialist chat: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


# ============== Recherche dans les connaissances ==============

@specialists_bp.route("/specialists/<specialist_id>/search", methods=["POST"])
@login_required
def search_knowledge(specialist_id: str):
    """Recherche dans les connaissances d'un spécialiste."""
    specialist = svc.get_specialist(specialist_id, get_user_id())
    if not specialist:
        return jsonify({"error": "Spécialiste non trouvé"}), 404
    
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    
    if not query:
        return jsonify({"error": "Query requise"}), 400
    
    try:
        results = svc.search_knowledge(specialist_id, query, top_k=data.get("top_k", 5))
        return jsonify({"results": results})
    except Exception as e:
        current_app.logger.error(f"Error searching knowledge: {e}")
        return jsonify({"error": str(e)}), 500
