import json
import re
from flask import jsonify, request, Response, current_app, stream_with_context
from . import api_chat_bp, get_history_service, get_llm_client, generate_title


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
    images = data.get("images", [])
    files = data.get("files", [])
    web_search = data.get("web_search", False)
    email_context = data.get("email_context", False)
    bookstack_context = data.get("bookstack_context", False)

    if not message and not images and not files:
        return jsonify({"error": "Message, images, or files required"}), 400

    svc = get_history_service()

    if not session_id:
        if not model:
            return jsonify({"error": "Model required for new session"}), 400
        session_id = svc.create_session(model)

    session = svc.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    current_model = model if model else session.get("model")
    session_system_prompt = session.get("system_prompt", "")
    session_model_config = session.get("model_config", {})

    try:
        from ....services.llm_config_service import get_default_system_prompt, get_default_options
        default_system_prompt = get_default_system_prompt()
        default_options = get_default_options()
    except Exception:
        default_system_prompt = ""
        default_options = {}

    system_prompt = session_system_prompt if session_system_prompt else default_system_prompt
    model_config = {**default_options, **session_model_config}

    # Build the full user message content
    full_message_parts = []
    if files:
        for f in files:
            file_content = f.get("content", "")
            filename = f.get("filename", "file")
            full_message_parts.append(f"[File: {filename}]\n```\n{file_content}\n```\n")
    if message:
        full_message_parts.append(message)
    full_message = "\n".join(full_message_parts) if full_message_parts else message or ""

    has_images = len(images) > 0
    user_content = full_message
    if has_images:
        user_content = f"[{len(images)} image(s) attached]\n\n{full_message}" if full_message else f"[{len(images)} image(s) attached]"

    svc.add_message(session_id, "user", user_content, images=images if images else None)

    # Get RAG context
    rag_context = ""
    try:
        from ....services.rag_service import get_context_for_query, init_db
        init_db()
        rag_context, sources = get_context_for_query(session_id, message or "")
    except Exception as e:
        current_app.logger.warning(f"RAG context retrieval failed: {e}")

    # Get web search context
    web_context = ""
    web_sources = []
    memory_context = ""
    memory_concepts = []

    if web_search and message:
        try:
            from ....services.web_search_service import search_web, format_search_context, get_searxng_url, get_config
            if get_searxng_url():
                web_search_config = get_config()
                results = search_web(message, max_results=web_search_config.get("max_results", 5))
                if results:
                    web_context = format_search_context(results)
                    web_sources = [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in results]
                    try:
                        from ....services.memory_graph_service import process_search_results
                        from flask_login import current_user as mem_user
                        user_id = int(mem_user.id) if mem_user.is_authenticated else 1
                        memory_context, memory_concepts = process_search_results(
                            user_id=user_id, query=message, search_results=web_sources, session_id=session_id
                        )
                    except Exception as mem_err:
                        current_app.logger.warning(f"Memory Graph processing failed: {mem_err}")
        except Exception as e:
            current_app.logger.warning(f"Web search failed: {e}")

    # Get email context
    email_ctx = ""
    email_summaries = []

    # Get Bookstack documentation context
    bookstack_ctx = ""
    bookstack_sources = []

    if bookstack_context and message:
        try:
            from ....services.bookstack_service import search_bookstack, format_bookstack_context, is_bookstack_available
            if is_bookstack_available():
                bs_results = search_bookstack(message)
                if bs_results:
                    bookstack_ctx = format_bookstack_context(bs_results)
                    bookstack_sources = [{"title": r.title, "url": r.url, "type": r.type, "content": r.content[:200]} for r in bs_results]
        except Exception as e:
            current_app.logger.warning(f"Bookstack search failed: {e}")

    if email_context and message:
        try:
            from ....services.email import (
                list_emails, format_email_context, is_email_available,
                get_email_actions_prompt, execute_all_email_actions
            )
            if is_email_available():
                emails = list_emails()
                if emails:
                    email_ctx = format_email_context(emails)
                    email_summaries = [
                        {"uid": e.uid, "subject": e.subject, "sender": e.sender,
                         "date": e.date, "is_read": e.is_read, "folder": e.folder}
                        for e in emails
                    ]
        except Exception as e:
            current_app.logger.warning(f"Email context failed: {e}")

    def generate():
        try:
            client = get_llm_client()
        except Exception as client_error:
            yield f"data: {json.dumps({'error': f'Erreur client LLM: {str(client_error)}'})}\n\n"
            return

        full_response = []
        full_thinking = []

        try:
            updated_session = svc.get_session(session_id)
            chat_messages = []

            effective_system = system_prompt

            if memory_context:
                effective_system = memory_context + "\n\n" + (effective_system or "")
            if bookstack_ctx:
                bs_instruction = (
                    "Tu as accès à la documentation Bookstack suivante. "
                    "Utilise ces informations pour répondre aux questions sur les procédures, "
                    "la documentation et les guides. Cite les sources quand c'est pertinent.\n\n"
                )
                effective_system = bs_instruction + bookstack_ctx + "\n\n" + (effective_system or "")
            if web_context:
                web_instruction = (
                    "Tu as accès aux résultats de recherche web suivants. "
                    "Utilise ces informations pour fournir des réponses à jour et précises. "
                    "Cite tes sources quand c'est pertinent.\n\n"
                )
                effective_system = web_instruction + web_context + "\n\n" + (effective_system or "")
            if email_ctx:
                email_actions_prompt = ""
                try:
                    from ....services.email import get_email_actions_prompt
                    email_actions_prompt = get_email_actions_prompt()
                except Exception:
                    pass
                email_instruction = (
                    "Tu as accès aux emails récents de l'utilisateur. "
                    "Tu peux les lire, y répondre, les transférer, les trier, "
                    "les supprimer, les taguer, et rédiger de nouveaux emails. "
                    "Utilise ces informations pour répondre aux questions de l'utilisateur "
                    "concernant ses emails.\n\n"
                )
                effective_system = email_instruction + email_ctx + "\n" + email_actions_prompt + "\n\n" + (effective_system or "")
            if rag_context:
                rag_instruction = (
                    "Tu as accès aux documents suivants fournis par l'utilisateur. "
                    "Utilise ces informations pour répondre aux questions de manière précise. "
                    "Si l'information n'est pas dans les documents, dis-le clairement.\n\n"
                )
                effective_system = rag_instruction + rag_context + "\n\n" + (effective_system or "")

            if effective_system:
                chat_messages.append({"role": "system", "content": effective_system})

            for m in updated_session["messages"]:
                msg_data = {"role": m["role"], "content": m["content"]}
                if m.get("images"):
                    msg_data["images"] = m["images"]
                chat_messages.append(msg_data)

            options = {}
            if model_config:
                for key, cast in [("temperature", float), ("num_ctx", int), ("top_p", float), ("top_k", int), ("repeat_penalty", float)]:
                    if key in model_config:
                        options[key] = cast(model_config[key])

            for chunk in client.chat_stream(
                messages=chat_messages, model=current_model,
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

                response_data = {
                    'role': 'assistant', 'content': content, 'thinking': thinking,
                    'done': done, 'session_id': session_id
                }
                if done and web_sources:
                    response_data['web_sources'] = web_sources
                if done and memory_concepts:
                    response_data['memory_concepts'] = memory_concepts
                if done and email_summaries:
                    response_data['email_context'] = email_summaries
                if done and bookstack_sources:
                    response_data['bookstack_sources'] = bookstack_sources
                yield f"data: {json.dumps(response_data)}\n\n"

            assistant_content = "".join(full_response)
            assistant_thinking = "".join(full_thinking) if full_thinking else None

            # Execute email actions if present
            email_action_results = []
            if email_context and "[EMAIL_ACTION:" in assistant_content:
                try:
                    from ....services.email import execute_all_email_actions
                    email_action_results, cleaned_content = execute_all_email_actions(assistant_content)
                    assistant_content = cleaned_content
                    if email_action_results:
                        yield f"data: {json.dumps({'email_actions': email_action_results, 'session_id': session_id})}\n\n"
                except Exception as ea_err:
                    current_app.logger.error(f"Email action execution failed: {ea_err}")

            extra_data = None
            if web_sources or memory_concepts or email_summaries or email_action_results or bookstack_sources:
                extra_data = {}
                if web_sources: extra_data["web_sources"] = web_sources
                if memory_concepts: extra_data["memory_concepts"] = memory_concepts
                if email_summaries: extra_data["email_context"] = email_summaries
                if email_action_results: extra_data["email_actions"] = email_action_results
                if bookstack_sources: extra_data["bookstack_sources"] = bookstack_sources

            svc.add_message(session_id, "assistant", assistant_content, thinking=assistant_thinking, extra_data=extra_data)

            # Auto-generate title
            try:
                session_data = svc.get_session(session_id)
                if session_data and session_data.get("title") == "New Chat":
                    user_messages = [m for m in session_data.get("messages", []) if m.get("role") == "user"]
                    if len(user_messages) == 1:
                        from ....services.llm_config_service import is_auto_title_enabled
                        if is_auto_title_enabled():
                            first_user_message = user_messages[0].get("content", "")
                            clean_message = first_user_message
                            if clean_message.startswith("["):
                                clean_message = re.sub(r'^\[\d+ image\(s\) attached\]\s*', '', clean_message, flags=re.IGNORECASE)
                                clean_message = re.sub(r'^\[File: [^\]]+\]\s*', '', clean_message, flags=re.MULTILINE)
                            clean_message = clean_message.strip()
                            new_title = generate_title(clean_message, current_model)
                            svc.update_session_settings(session_id, title=new_title)
                            yield f"data: {json.dumps({'title_update': new_title, 'session_id': session_id})}\n\n"
            except Exception as e:
                current_app.logger.error(f"[Title Gen] Error generating title: {e}", exc_info=True)

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
