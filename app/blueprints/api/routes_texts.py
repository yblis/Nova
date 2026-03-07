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
        length=data.get("length", "Moyen"),
        paraphrase=data.get("paraphrase", False)
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
    """Génère un email, une réponse, ou une lettre de motivation."""
    from ...services.text_tools_service import generate_email as svc_generate_email
    
    data = request.json or {}
    mode = data.get("mode", "generate")
    email_type = data.get("email_type", "").strip()
    content = data.get("content", "").strip()
    model = data.get("model", "")
    
    if mode == "reply":
        email_received = data.get("email_received", "").strip()
        if not email_received:
            return jsonify({"error": "L'email reçu est requis"}), 400
    elif mode == "cover_letter":
        job_title = data.get("job_title", "").strip()
        company = data.get("company", "").strip()
        if not job_title or not company:
            return jsonify({"error": "Le poste et l'entreprise sont requis"}), 400
    else:
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
        tone=data.get("tone", "Professionnel"),
        mode=mode,
        email_received=data.get("email_received", ""),
        reply_type=data.get("reply_type", "Réponse neutre"),
        job_title=data.get("job_title", ""),
        company=data.get("company", ""),
        profile=data.get("profile", "")
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

# ========== Nouveaux outils texte ==========

@api_texts_bp.route("/texts/extract", methods=["POST"])
def extract_data():
    """Extrait des données structurées depuis du texte brut."""
    from ...services.text_tools_service import extract_data as svc_extract_data
    
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    output_format = data.get("output_format", "JSON")
    
    if not text:
        return jsonify({"error": "Le texte est requis"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400
    
    result = svc_extract_data(text=text, model=model, output_format=output_format)
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


@api_texts_bp.route("/texts/simplify", methods=["POST"])
def simplify_text():
    """Simplifie un texte complexe."""
    from ...services.text_tools_service import simplify_text as svc_simplify_text
    
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    level = data.get("level", "Grand public")
    
    if not text:
        return jsonify({"error": "Le texte est requis"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400
    
    result = svc_simplify_text(text=text, model=model, level=level)
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


@api_texts_bp.route("/texts/expand", methods=["POST"])
def expand_text():
    """Développe une ébauche en texte complet."""
    from ...services.text_tools_service import expand_text as svc_expand_text
    
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    tone = data.get("tone", "Professionnel")
    length = data.get("length", "Moyen")
    
    if not text:
        return jsonify({"error": "Le texte est requis"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400
    
    result = svc_expand_text(text=text, model=model, tone=tone, length=length)
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


@api_texts_bp.route("/texts/todolist", methods=["POST"])
def generate_todolist():
    """Extrait un plan d'action depuis des notes."""
    from ...services.text_tools_service import generate_todolist as svc_generate_todolist
    
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    
    if not text:
        return jsonify({"error": "Le texte est requis"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400
    
    result = svc_generate_todolist(text=text, model=model)
    
    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500

# ========== Génération de scripts ==========

@api_texts_bp.route("/texts/generate-script", methods=["POST"])
def generate_script():
    from ...services.text_tools_service import generate_script as svc_generate_script

    data = request.json or {}
    description = data.get("description", "").strip()
    model = data.get("model", "")
    language = data.get("language", "Bash")
    commented = data.get("commented", False)
    strict_mode = data.get("strict_mode", False)

    if not description:
        return jsonify({"error": "La description est requise"}), 400
    if len(description) > 10000:
        return jsonify({"error": "La description ne doit pas dépasser 10 000 caractères"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400

    allowed_languages = {"Bash", "Python", "PowerShell", "Auto"}
    if language not in allowed_languages:
        return jsonify({"error": f"Langage invalide. Valeurs acceptées : {', '.join(sorted(allowed_languages))}"}), 400

    result = svc_generate_script(
        description=description,
        model=model,
        language=language,
        commented=bool(commented),
        strict_mode=bool(strict_mode)
    )

    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


# ========== Génération de diagrammes Mermaid ==========

@api_texts_bp.route("/texts/generate-mermaid", methods=["POST"])
def generate_mermaid():
    from ...services.text_tools_service import generate_mermaid as svc_generate_mermaid

    data = request.json or {}
    description = data.get("description", "").strip()
    model = data.get("model", "")
    previous_code = data.get("previous_code", "").strip()
    image_base64 = data.get("image_base64", "").strip()

    # Strip data URI prefix if present (e.g. "data:image/png;base64,...")
    if image_base64 and ";base64," in image_base64:
        image_base64 = image_base64.split(";base64,", 1)[1]

    if not description and not image_base64:
        return jsonify({"error": "Une description ou une image est requise"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400

    result = svc_generate_mermaid(
        description=description or "Analyse cette image et génère un diagramme Mermaid correspondant.",
        model=model,
        previous_code=previous_code,
        image_base64=image_base64
    )

    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


# ========== Génération de documentation ==========

@api_texts_bp.route("/texts/generate-documentation", methods=["POST"])
def generate_documentation():
    from ...services.text_tools_service import generate_documentation as svc_generate_documentation

    data = request.json or {}

    outline = data.get("outline", "").strip()
    model = data.get("model", "")
    style = data.get("style", "Technique")
    previous_doc = data.get("previous_doc", "").strip()
    improvement_prompt = data.get("improvement_prompt", "").strip()

    # Process source images (for analysis context)
    source_images_raw = data.get("source_images", [])
    source_images = []
    for img in source_images_raw:
        img = img.strip() if isinstance(img, str) else ""
        if img and ";base64," in img:
            img = img.split(";base64,", 1)[1]
        if img:
            source_images.append(img)

    # Process embed images (to place inline in doc)
    embed_images_raw = data.get("embed_images", [])
    embed_images = []
    for item in embed_images_raw:
        if isinstance(item, dict):
            img_b64 = item.get("base64", "").strip()
            if img_b64 and ";base64," in img_b64:
                img_b64 = img_b64.split(";base64,", 1)[1]
            if img_b64:
                embed_images.append({"id": item.get("id", ""), "base64": img_b64})

    if not outline and not source_images and not embed_images and not (previous_doc and improvement_prompt):
        return jsonify({"error": "La trame, des images ou un prompt d'amélioration est requis"}), 400
    if not model:
        return jsonify({"error": "Le modèle est requis"}), 400

    result = svc_generate_documentation(
        outline=outline,
        model=model,
        style=style,
        previous_doc=previous_doc,
        improvement_prompt=improvement_prompt,
        source_images=source_images,
        embed_images=embed_images
    )

    if result.get("success"):
        return jsonify(result)
    return jsonify(result), 500


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


@api_texts_bp.route("/texts/generate-recipe", methods=["POST"])
def generate_recipe():
    """Génère une recette à partir d'ingrédients ou d'une idée."""
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    diet = data.get("diet", "")
    time_limit = data.get("time", "")
    servings = data.get("servings", "")

    if not text:
        return jsonify({"error": "Veuillez décrire votre idée de recette ou lister vos ingrédients"}), 400
    if not model:
        return jsonify({"error": "Aucun modèle sélectionné"}), 400

    from app.services.text_tools_service import generate_recipe as svc_generate_recipe
    result = svc_generate_recipe(text, model, diet=diet, time=time_limit, servings=servings)

    if result.get("success"):
        return jsonify({"result": result["result"]})
    return jsonify({"error": result.get("error", "Erreur inconnue")}), 500


@api_texts_bp.route("/texts/generate-fitness", methods=["POST"])
def generate_fitness():
    """Génère un programme sportif personnalisé."""
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    goal = data.get("goal", "")
    equipment = data.get("equipment", "")
    level = data.get("level", "")

    if not text:
        return jsonify({"error": "Veuillez décrire votre objectif sportif"}), 400
    if not model:
        return jsonify({"error": "Aucun modèle sélectionné"}), 400

    from app.services.text_tools_service import generate_fitness as svc_generate_fitness
    result = svc_generate_fitness(text, model, goal=goal, equipment=equipment, level=level)

    if result.get("success"):
        return jsonify({"result": result["result"]})
    return jsonify({"error": result.get("error", "Erreur inconnue")}), 500


@api_texts_bp.route("/texts/generate-admin-letter", methods=["POST"])
def generate_admin_letter():
    """Génère une lettre administrative formelle."""
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    letter_type = data.get("letter_type", "")

    if not text:
        return jsonify({"error": "Veuillez décrire la situation"}), 400
    if not model:
        return jsonify({"error": "Aucun modèle sélectionné"}), 400

    from app.services.text_tools_service import generate_admin_letter as svc_admin_letter
    result = svc_admin_letter(text, model, letter_type=letter_type)

    if result.get("success"):
        return jsonify({"result": result["result"]})
    return jsonify({"error": result.get("error", "Erreur inconnue")}), 500


@api_texts_bp.route("/texts/generate-flashcards", methods=["POST"])
def generate_flashcards():
    """Génère des flashcards à partir de contenu."""
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    difficulty = data.get("difficulty", "Intermédiaire")
    card_format = data.get("card_format", "Question/Réponse")

    if not text:
        return jsonify({"error": "Veuillez fournir un contenu à transformer en flashcards"}), 400
    if not model:
        return jsonify({"error": "Aucun modèle sélectionné"}), 400

    from app.services.text_tools_service import generate_flashcards as svc_flashcards
    result = svc_flashcards(text, model, difficulty=difficulty, card_format=card_format)

    if result.get("success"):
        return jsonify({"result": result["result"]})
    return jsonify({"error": result.get("error", "Erreur inconnue")}), 500


@api_texts_bp.route("/texts/explain-eli5", methods=["POST"])
def explain_eli5():
    """Explique un concept de manière simplifiée."""
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    level = data.get("level", "Grand public")

    if not text:
        return jsonify({"error": "Veuillez fournir un concept à expliquer"}), 400
    if not model:
        return jsonify({"error": "Aucun modèle sélectionné"}), 400

    from app.services.text_tools_service import explain_eli5 as svc_eli5
    result = svc_eli5(text, model, level=level)

    if result.get("success"):
        return jsonify({"result": result["result"]})
    return jsonify({"error": result.get("error", "Erreur inconnue")}), 500


@api_texts_bp.route("/texts/generate-speech", methods=["POST"])
def generate_speech():
    """Génère un discours pour une occasion donnée."""
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    occasion = data.get("occasion", "")
    tone = data.get("tone", "")

    if not text:
        return jsonify({"error": "Veuillez décrire le contexte du discours"}), 400
    if not model:
        return jsonify({"error": "Aucun modèle sélectionné"}), 400

    from app.services.text_tools_service import generate_speech as svc_speech
    result = svc_speech(text, model, occasion=occasion, tone=tone)

    if result.get("success"):
        return jsonify({"result": result["result"]})
    return jsonify({"error": result.get("error", "Erreur inconnue")}), 500


@api_texts_bp.route("/texts/compare-decide", methods=["POST"])
def compare_decide():
    """Analyse comparative pour aide à la décision."""
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")

    if not text:
        return jsonify({"error": "Veuillez décrire les options à comparer"}), 400
    if not model:
        return jsonify({"error": "Aucun modèle sélectionné"}), 400

    from app.services.text_tools_service import compare_decide as svc_decide
    result = svc_decide(text, model)

    if result.get("success"):
        return jsonify({"result": result["result"]})
    return jsonify({"error": result.get("error", "Erreur inconnue")}), 500


@api_texts_bp.route("/texts/generate-regex", methods=["POST"])
def generate_regex():
    """Génère une regex à partir d'une description en langage naturel."""
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")

    if not text:
        return jsonify({"error": "Veuillez décrire ce que la regex doit capturer"}), 400
    if not model:
        return jsonify({"error": "Aucun modèle sélectionné"}), 400

    from app.services.text_tools_service import generate_regex as svc_regex
    result = svc_regex(text, model)

    if result.get("success"):
        return jsonify({"result": result["result"]})
    return jsonify({"error": result.get("error", "Erreur inconnue")}), 500


@api_texts_bp.route("/texts/convert-format", methods=["POST"])
def convert_format():
    """Convertit des données entre formats (JSON, YAML, XML, CSV, Tableau)."""
    data = request.json or {}
    text = data.get("text", "").strip()
    model = data.get("model", "")
    target_format = data.get("target_format", "JSON")

    if not text:
        return jsonify({"error": "Veuillez fournir les données à convertir"}), 400
    if not model:
        return jsonify({"error": "Aucun modèle sélectionné"}), 400

    from app.services.text_tools_service import convert_format as svc_convert
    result = svc_convert(text, model, target_format=target_format)

    if result.get("success"):
        return jsonify({"result": result["result"]})
    return jsonify({"error": result.get("error", "Erreur inconnue")}), 500


@api_texts_bp.route("/texts/proxy-image", methods=["POST"])
def proxy_image():
    """Proxy pour télécharger une image externe et la renvoyer en base64 (contourne CORS)."""
    import requests as http_requests
    import base64

    data = request.json or {}
    url = data.get("url", "").strip()

    if not url or not url.startswith("http"):
        return jsonify({"error": "URL invalide"}), 400

    try:
        resp = http_requests.get(url, timeout=10, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "image/png")
        if not content_type.startswith("image/"):
            return jsonify({"error": "Le contenu n'est pas une image"}), 400

        # Limit to 10 MB
        content = resp.content
        if len(content) > 10 * 1024 * 1024:
            return jsonify({"error": "Image trop volumineuse (max 10 Mo)"}), 400

        b64 = base64.b64encode(content).decode("utf-8")
        data_uri = f"data:{content_type};base64,{b64}"

        return jsonify({"success": True, "base64": data_uri})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
