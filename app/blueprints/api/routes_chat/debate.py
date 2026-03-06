import json
import uuid
from flask import jsonify, request, Response, current_app, stream_with_context
from . import api_chat_bp, get_history_service
from ....services.debate_service import get_debate_service, Participant


@api_chat_bp.route("/chat/debate/providers", methods=["GET"])
def list_debate_providers():
    """Liste les providers disponibles pour le mode débat."""
    try:
        service = get_debate_service()
        providers = service.get_available_providers()
        return jsonify({"providers": providers})
    except Exception as e:
        current_app.logger.error(f"Error listing debate providers: {e}")
        return jsonify({"providers": [], "error": str(e)}), 500


@api_chat_bp.route("/chat/debate", methods=["POST"])
def generate_debate():
    """Stream des réponses multi-LLM en mode débat."""
    data = request.json or {}
    session_id = data.get("session_id")
    message = data.get("message", "").strip()
    participants_data = data.get("participants", [])
    mode = data.get("mode", "parallel")
    rounds = data.get("rounds", 1)
    global_system_prompt = data.get("system_prompt", "")

    if not message:
        return jsonify({"error": "Message required"}), 400
    if not participants_data or len(participants_data) < 2:
        return jsonify({"error": "At least 2 participants required"}), 400
    if len(participants_data) > 4:
        return jsonify({"error": "Maximum 4 participants allowed"}), 400

    svc = get_history_service()
    debate_service = get_debate_service()

    if not session_id:
        first_model = participants_data[0].get("model", "debate")
        session_id = svc.create_session(first_model, "Debate: " + message[:30])

    session = svc.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    participants = []
    for i, p_data in enumerate(participants_data):
        provider_id = p_data.get("provider_id")
        if not provider_id:
            return jsonify({"error": f"provider_id required for participant {i}"}), 400
        model = p_data.get("model")
        if not model:
            return jsonify({"error": f"model required for participant {i}"}), 400

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

        if global_system_prompt:
            participant.system_prompt = global_system_prompt
        else:
            other_participants = [Participant.from_dict(pd) for pd in participants_data if pd != p_data]
            participant.system_prompt = debate_service.build_debate_system_prompt(
                participant, other_participants, message
            )
        participants.append(participant)

    participants_info = [
        {"id": p.id, "name": p.name, "model": p.model, "provider_id": p.provider_id, "color": p.color}
        for p in participants
    ]
    svc.update_session_settings(session_id, model_config={"debate_participants": participants_info, "debate_mode": mode})
    svc.add_message(session_id, "user", message)

    session_messages = session.get("messages", [])
    context_messages = [{"role": m["role"], "content": m["content"]} for m in session_messages]

    def generate():
        try:
            yield f"data: {json.dumps({'session_id': session_id, 'start': True})}\n\n"
            responses = {p.id: {"name": p.name, "color": p.color, "content": ""} for p in participants}

            if mode == "parallel":
                for chunk in debate_service.parallel_generate(
                    participants=participants,
                    messages=context_messages + [{"role": "user", "content": message}]
                ):
                    participant_id = chunk.get("participant_id")
                    if participant_id and chunk.get("content"):
                        responses[participant_id]["content"] += chunk.get("content", "")
                    yield f"data: {json.dumps(chunk)}\n\n"
            else:
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

            for participant_id, resp_data in responses.items():
                if resp_data["content"]:
                    participant = next((p for p in participants if p.id == participant_id), None)
                    if participant:
                        formatted_content = f"[{resp_data['name']}]: {resp_data['content']}"
                        svc.add_message(
                            session_id, "assistant", formatted_content,
                            extra_data={
                                "participant_id": participant_id,
                                "participant_name": resp_data["name"],
                                "participant_color": resp_data["color"]
                            }
                        )

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
