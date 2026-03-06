from flask import jsonify, request, current_app
from . import api_chat_bp


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
        from ....services.memory_graph_service import delete_node_by_concept
        from ....services.chat_history_pg import ChatHistoryService

        user_id = 1

        result = delete_node_by_concept(user_id, concept)
        current_app.logger.info(f"[Memory] delete_node_by_concept('{concept}') returned: {result}")

        if session_id and message_index is not None and remaining_concepts is not None:
            try:
                history_service = ChatHistoryService()
                session = history_service.get_session(session_id)
                if session and 'messages' in session and message_index < len(session['messages']):
                    msg = session['messages'][message_index]
                    extra = msg.get('extra_data') or {}
                    extra['memory_concepts'] = remaining_concepts
                    history_service.update_message_extra_data(session_id, message_index, extra)
                    current_app.logger.info(f"[Memory] Updated extra_data for message {message_index} in session {session_id}")
            except Exception as e:
                current_app.logger.error(f"[Memory] Failed to update message extra_data: {e}")

        return jsonify({"status": "deleted" if result else "not_found_in_graph", "concept": concept})

    except Exception as e:
        current_app.logger.error(f"Error deleting concept: {e}")
        return jsonify({"error": str(e)}), 500
