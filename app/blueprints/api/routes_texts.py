"""
Routes API pour les outils de traitement de texte.

Endpoints pour la reformulation, traduction, correction, 
génération d'email, génération de prompt et gestion de l'historique.
"""

from flask import Blueprint, jsonify, request, current_app

api_texts_bp = Blueprint("api_texts", __name__)


@api_texts_bp.route("/texts/reformulate", methods=["POST"])
def reformulate():
    """Reformule un texte selon les options spécifiées."""
    from ...services.text_tools_service import reformulate as svc_reformulate
    
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    
    if not text:
        return jsonify({"error": "Le texte est requis"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400
    
    result = svc_reformulate(
        text=text,
        model=model,
        context=data.get("context", ""),
        add_emojis=data.get("add_emojis", False),
        tone=data.get("tone", "Professionnel"),
        format_type=data.get("format", "Paragraphe"),
        length=data.get("length", "Moyen")
    )
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


@api_texts_bp.route("/texts/translate", methods=["POST"])
def translate():
    """Traduit un texte vers la langue cible."""
    from ...services.text_tools_service import translate as svc_translate
    
    data = request.json or {}
    text = data.get("text", "").strip()
    target_language = data.get("target_language", "")
    model = data.get("model", "")
    
    if not text:
        return jsonify({"error": "Le texte est requis"}), 400
    if not target_language:
        return jsonify({"error": "La langue cible est requise"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400
    
    result = svc_translate(
        text=text,
        target_language=target_language,
        model=model
    )
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


@api_texts_bp.route("/texts/correct", methods=["POST"])
def correct():
    """Corrige un texte selon les options spécifiées."""
    from ...services.text_tools_service import correct as svc_correct
    
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    
    if not text:
        return jsonify({"error": "Le texte est requis"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400
    
    result = svc_correct(
        text=text,
        model=model,
        syntax=data.get("syntax", True),
        grammar=data.get("grammar", True),
        spelling=data.get("spelling", True),
        punctuation=data.get("punctuation", True),
        style=data.get("style", False),
        synonyms=data.get("synonyms", False)
    )
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


@api_texts_bp.route("/texts/generate-email", methods=["POST"])
def generate_email():
    """Génère un email structuré."""
    from ...services.text_tools_service import generate_email as svc_generate_email
    
    data = request.json or {}
    email_type = data.get("email_type", "").strip()
    content = data.get("content", "").strip()
    model = data.get("model", "")
    
    if not email_type:
        return jsonify({"error": "Le type d'email est requis"}), 400
    if not content:
        return jsonify({"error": "Le contenu est requis"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400
    
    result = svc_generate_email(
        email_type=email_type,
        content=content,
        model=model,
        sender_name=data.get("sender_name", ""),
        tone=data.get("tone", "Professionnel")
    )
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


@api_texts_bp.route("/texts/generate-prompt", methods=["POST"])
def generate_prompt():
    """Génère un prompt IA optimisé."""
    from ...services.text_tools_service import generate_prompt as svc_generate_prompt
    
    data = request.json or {}
    description = data.get("description", "").strip()
    model = data.get("model", "")
    
    if not description:
        return jsonify({"error": "La description est requise"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400
    
    result = svc_generate_prompt(
        description=description,
        model=model
    )
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


@api_texts_bp.route("/texts/summarize", methods=["POST"])
def summarize():
    """Génère un résumé du texte."""
    from ...services.text_tools_service import generate_summary as svc_generate_summary
    
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    session_id = data.get("session_id")
    
    current_app.logger.info(f"Summarize request - Session: {session_id}, Text length: {len(text)}")
    
    if not text and not session_id:
        return jsonify({"error": "Le texte ou un document est requis"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400
    
    result = svc_generate_summary(
        text=text,
        model=model,
        session_id=session_id
    )
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


@api_texts_bp.route("/texts/history", methods=["GET"])
def get_history():
    """Récupère l'historique des opérations."""
    from ...services.text_tools_service import get_history as svc_get_history
    
    filter_type = request.args.get("type")
    limit = request.args.get("limit", 50, type=int)
    
    history = svc_get_history(filter_type=filter_type, limit=limit)
    return jsonify({"history": history})


@api_texts_bp.route("/texts/history/<item_id>", methods=["GET"])
def get_history_item(item_id):
    """Récupère un élément spécifique de l'historique."""
    from ...services.text_tools_service import get_history_item as svc_get_history_item
    
    item = svc_get_history_item(item_id)
    if item:
        return jsonify(item)
    return jsonify({"error": "Élément non trouvé"}), 404


@api_texts_bp.route("/texts/history", methods=["DELETE"])
def clear_history():
    """Efface tout l'historique."""
    from ...services.text_tools_service import clear_history as svc_clear_history
    
    if svc_clear_history():
        return jsonify({"status": "cleared"})
    return jsonify({"error": "Erreur lors de la suppression"}), 500


@api_texts_bp.route("/texts/history/<item_id>", methods=["DELETE"])
def delete_history_item(item_id):
    """Supprime un élément de l'historique."""
    from ...services.text_tools_service import delete_history_item as svc_delete_history_item
    
    if svc_delete_history_item(item_id):
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Élément non trouvé"}), 404


# ========== Configuration des prompts ==========

@api_texts_bp.route("/texts/prompts", methods=["GET"])
def get_prompts():
    """Récupère tous les prompts configurés."""
    from ...services.text_prompts_service import get_prompts as svc_get_prompts
    return jsonify({"prompts": svc_get_prompts()})


@api_texts_bp.route("/texts/prompts", methods=["POST"])
def set_prompts():
    """Met à jour les prompts."""
    from ...services.text_prompts_service import set_prompts as svc_set_prompts
    
    data = request.json or {}
    prompts = data.get("prompts", {})
    
    if svc_set_prompts(prompts):
        return jsonify({"status": "updated"})
    return jsonify({"error": "Erreur lors de la mise à jour"}), 500


@api_texts_bp.route("/texts/prompts/reset", methods=["POST"])
def reset_prompts():
    """Réinitialise tous les prompts aux valeurs par défaut."""
    from ...services.text_prompts_service import reset_prompts as svc_reset_prompts
    
    if svc_reset_prompts():
        return jsonify({"status": "reset"})
    return jsonify({"error": "Erreur lors de la réinitialisation"}), 500


@api_texts_bp.route("/texts/options", methods=["GET"])
def get_options():
    """Récupère les options personnalisables."""
    from ...services.text_prompts_service import get_options as svc_get_options
    return jsonify({"options": svc_get_options()})


@api_texts_bp.route("/texts/options", methods=["POST"])
def add_option():
    """Ajoute une option personnalisée."""
    from ...services.text_prompts_service import add_option as svc_add_option
    
    data = request.json or {}
    option_type = data.get("type", "")
    value = data.get("value", "").strip()
    
    if not option_type or not value:
        return jsonify({"error": "Type et valeur requis"}), 400
    
    if svc_add_option(option_type, value):
        return jsonify({"status": "added"})
    return jsonify({"error": "Type d'option invalide"}), 400


@api_texts_bp.route("/texts/options", methods=["DELETE"])
def remove_option():
    """Retire une option personnalisée."""
    from ...services.text_prompts_service import remove_option as svc_remove_option
    
    data = request.json or {}
    option_type = data.get("type", "")
    value = data.get("value", "")
    
    if not option_type or not value:
        return jsonify({"error": "Type et valeur requis"}), 400
    
    if svc_remove_option(option_type, value):
        return jsonify({"status": "removed"})
    return jsonify({"error": "Type d'option invalide ou valeur non trouvée"}), 400


# ========== Génération de CV ==========

@api_texts_bp.route("/resume/generate", methods=["POST"])
def generate_resume():
    """Génère un CV au format HTML via le LLM."""
    import json
    from ...services.text_prompts_service import get_prompt
    
    # Import LLM client helper
    def _get_llm_client():
        """Retourne le client LLM actif (multi-provider)."""
        from ...services.llm_clients import get_active_client
        from ...services.llm_error_handler import LLMError
        
        try:
            client = get_active_client()
            if client:
                return client
        except LLMError:
            pass
        
        # Fallback sur OllamaClient si aucun provider actif
        from ...services.ollama_client import OllamaClient
        from ...utils import get_effective_ollama_base_url
        return OllamaClient(
            base_url=get_effective_ollama_base_url(),
            connect_timeout=current_app.config.get("HTTP_CONNECT_TIMEOUT", 10),
            read_timeout=current_app.config.get("HTTP_READ_TIMEOUT", 120),
        )
    
    data = request.json or {}
    resume_data = data.get("data", {})
    style = data.get("style", "modern")
    model = data.get("model")
    
    if not resume_data:
        return jsonify({"error": "Les données du CV sont requises"}), 400
    if not model:
        return jsonify({"error": "Le modèle LLM est requis"}), 400
    
    try:
        # Récupérer le prompt système
        system_prompt = get_prompt("resume_generation")
        
        # Préparer les données JSON
        data_json = json.dumps(resume_data, ensure_ascii=False, indent=2)
        
        # Construire le prompt utilisateur
        user_prompt = system_prompt.format(
            data_json=data_json,
            style=style.upper()
        )
        
        # Appeler le LLM
        client = _get_llm_client()
        response = client.chat(
            messages=[{"role": "user", "content": user_prompt}],
            model=model,
            stream=False
        )
        
        html_content = response.get("message", {}).get("content", "").strip()
        
        # Nettoyer le HTML (enlever les balises markdown si présentes)
        if html_content.startswith("```html"):
            html_content = html_content[7:]
        if html_content.startswith("```"):
            html_content = html_content[3:]
        if html_content.endswith("```"):
            html_content = html_content[:-3]
        html_content = html_content.strip()
        
        return jsonify({
            "success": True,
            "html": html_content
        })
            
    except Exception as e:
        error_msg = str(e)
        current_app.logger.error(f"Resume generation error: {error_msg}")
        
        # Nettoyage des messages d'erreur Google API trop verbeux
        if "429" in error_msg or "Quota exceeded" in error_msg:
            clean_error = "Quota dépassé pour ce modèle (429). Veuillez réessayer plus tard ou changer de modèle."
        elif "violations" in error_msg and "quota" in error_msg:
            clean_error = "Quota dépassé. Veuillez réessayer ultérieurement."
        else:
            # Garder le message court pour l'affichage
            clean_error = error_msg.split('[')[0].strip() if '[' in error_msg else error_msg
            if len(clean_error) > 150:
                clean_error = clean_error[:150] + "..."
                
        return jsonify({
            "success": False,
            "error": clean_error
        }), 500

