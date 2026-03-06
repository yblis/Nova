"""
Service des outils de traitement de texte.

Ce service fournit les fonctionnalités de reformulation, traduction,
correction, génération d'email et génération de prompt IA.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import current_app

from .text_prompts_service import get_prompt


def _get_llm_client():
    """Retourne le client LLM actif (multi-provider)."""
    from .llm_clients import get_active_client
    from .llm_error_handler import LLMError

    try:
        client = get_active_client()
        if client:
            return client
    except LLMError:
        pass

    # Fallback sur OllamaClient si aucun provider actif
    from .ollama_client import OllamaClient
    from ..utils import get_effective_ollama_base_url
    from flask import current_app
    return OllamaClient(
        base_url=get_effective_ollama_base_url(),
        connect_timeout=current_app.config.get("HTTP_CONNECT_TIMEOUT", 10),
        read_timeout=current_app.config.get("HTTP_READ_TIMEOUT", 120),
    )


def _get_history_path() -> str:
    """Retourne le chemin du fichier d'historique."""
    try:
        return os.path.join(current_app.root_path, "data", "text_tools_history.json")
    except RuntimeError:
        return os.path.join(os.path.dirname(__file__), "..", "data", "text_tools_history.json")


def _load_history() -> List[Dict[str, Any]]:
    """Charge l'historique depuis le fichier JSON."""
    history_path = _get_history_path()
    try:
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _save_history(history: List[Dict[str, Any]]) -> bool:
    """Sauvegarde l'historique dans le fichier JSON."""
    history_path = _get_history_path()
    try:
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f"Failed to save text tools history: {e}")
        except RuntimeError:
            pass
        return False


def _add_to_history(entry: Dict[str, Any]) -> str:
    """Ajoute une entrée à l'historique et retourne son ID."""
    history = _load_history()
    entry_id = str(uuid.uuid4())
    entry["id"] = entry_id
    entry["created_at"] = datetime.utcnow().isoformat()
    history.insert(0, entry)  # Ajouter au début
    # Limiter à 100 entrées
    history = history[:100]
    _save_history(history)
    return entry_id


def reformulate(
    text: str,
    model: str,
    context: str = "",
    add_emojis: bool = False,
    tone: str = "Professionnel",
    format_type: str = "Paragraphe",
    length: str = "Moyen",
    paraphrase: bool = False
) -> Dict[str, Any]:
    """
    Reformule un texte selon les options spécifiées.
    
    Args:
        text: Texte à reformuler
        model: Modèle LLM à utiliser
        context: Contexte optionnel
        add_emojis: Ajouter des emojis
        tone: Ton de la reformulation
        format_type: Format de sortie
        length: Longueur souhaitée
    
    Returns:
        Dict avec le résultat et les métadonnées
    """
    client = _get_llm_client()
    
    # Calculer le nombre de mots et la cible selon la longueur
    word_count = len(text.split())
    if length.lower() == "court":
        target_words = max(10, int(word_count * 0.4))
        length_instruction = f"{length} (~{target_words} mots max, condense au maximum)"
    elif length.lower() == "long":
        target_words = int(word_count * 1.8)
        length_instruction = f"{length} (~{target_words} mots min, développe avec des détails)"
    else:
        length_instruction = f"{length} (~{word_count} mots, longueur similaire)"
    
    if paraphrase:
        system_prompt = get_prompt("paraphrase")
        user_prompt_parts = []
        user_prompt_parts.append("━━━ CONSIGNES OBLIGATOIRES ━━━")
        user_prompt_parts.append(f"🎯 TON : {tone}")
        user_prompt_parts.append(f"📐 FORMAT : {format_type}")
        user_prompt_parts.append(f"📏 LONGUEUR : {length_instruction}")
        if add_emojis:
            user_prompt_parts.append("😀 EMOJIS : Oui, ajoute des emojis pertinents")
        user_prompt_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        user_prompt_parts.append(f"\nTexte à paraphraser ({word_count} mots) :\n{text}")
        user_prompt = "\n".join(user_prompt_parts)
    else:
        system_prompt = get_prompt("reformulation")
        
        # Consignes AVANT le texte pour qu'elles soient prioritaires
        user_prompt_parts = []
        user_prompt_parts.append("━━━ CONSIGNES OBLIGATOIRES ━━━")
        user_prompt_parts.append(f"🎯 TON : {tone}")
        user_prompt_parts.append(f"📐 FORMAT : {format_type}")
        user_prompt_parts.append(f"📏 LONGUEUR : {length_instruction}")
        if add_emojis:
            user_prompt_parts.append("😀 EMOJIS : Oui, ajoute des emojis pertinents")
        if context:
            user_prompt_parts.append(f"📝 CONTEXTE : {context}")
        user_prompt_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        user_prompt_parts.append(f"\nTexte à reformuler ({word_count} mots) :\n{text}")
        
        user_prompt = "\n".join(user_prompt_parts)
    
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            stream=False
        )
        
        result = response.get("message", {}).get("content", "")
        
        # Sauvegarder dans l'historique
        _add_to_history({
            "type": "paraphrase" if paraphrase else "reformulation",
            "input": text,
            "output": result,
            "options": {
                "context": context,
                "add_emojis": add_emojis,
                "tone": tone,
                "format": format_type,
                "length": length,
                "paraphrase": paraphrase
            },
            "model": model
        })
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def translate(text: str, target_language: str, model: str) -> Dict[str, Any]:
    """
    Traduit un texte vers la langue cible.
    
    Args:
        text: Texte à traduire
        target_language: Langue cible
        model: Modèle LLM à utiliser
    
    Returns:
        Dict avec le résultat et les métadonnées
    """
    client = _get_llm_client()
    system_prompt = get_prompt("translation").replace("{target_language}", target_language)
    
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            model=model,
            stream=False
        )
        
        result = response.get("message", {}).get("content", "")
        
        _add_to_history({
            "type": "translation",
            "input": text,
            "output": result,
            "options": {"target_language": target_language},
            "model": model
        })
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def correct(
    text: str,
    model: str,
    syntax: bool = True,
    grammar: bool = True,
    spelling: bool = True,
    punctuation: bool = True,
    style: bool = False,
    synonyms: bool = False
) -> Dict[str, Any]:
    """
    Corrige un texte selon les options spécifiées.
    
    Args:
        text: Texte à corriger
        model: Modèle LLM à utiliser
        syntax: Corriger la syntaxe
        grammar: Corriger la grammaire
        spelling: Corriger l'orthographe
        punctuation: Corriger la ponctuation
        style: Améliorer le style
        synonyms: Suggérer des synonymes
    
    Returns:
        Dict avec le texte corrigé et éventuellement les synonymes
    """
    client = _get_llm_client()
    system_prompt = get_prompt("correction")
    
    # Construire les options actives
    options_list = []
    if syntax:
        options_list.append("Correction syntaxique")
    if grammar:
        options_list.append("Correction grammaticale")
    if spelling:
        options_list.append("Correction orthographique")
    if punctuation:
        options_list.append("Correction de la ponctuation")
    if style:
        options_list.append("Amélioration du style")
    if synonyms:
        options_list.append("Suggestions de synonymes")
    
    user_prompt = f"""Texte à corriger:
{text}

Options actives: {', '.join(options_list)}

{"Active l'option 'Suggestions de synonymes'." if synonyms else "N'inclus PAS de suggestions de synonymes."}"""
    
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            stream=False
        )
        
        result_text = response.get("message", {}).get("content", "")
        
        # Parser le résultat si synonymes demandés
        corrected_text = result_text
        synonyms_dict = {}
        
        if synonyms and "===TEXTE CORRIGÉ===" in result_text:
            parts = result_text.split("===SYNONYMES===")
            if len(parts) >= 1:
                corrected_part = parts[0].replace("===TEXTE CORRIGÉ===", "").strip()
                corrected_text = corrected_part
            if len(parts) >= 2:
                synonyms_text = parts[1].strip()
                for line in synonyms_text.split("\n"):
                    if ":" in line:
                        word, syns = line.split(":", 1)
                        synonyms_dict[word.strip()] = [s.strip() for s in syns.split(",")]
        
        _add_to_history({
            "type": "correction",
            "input": text,
            "output": corrected_text,
            "options": {
                "syntax": syntax,
                "grammar": grammar,
                "spelling": spelling,
                "punctuation": punctuation,
                "style": style,
                "synonyms": synonyms
            },
            "model": model
        })
        
        return {
            "success": True,
            "result": corrected_text,
            "synonyms": synonyms_dict if synonyms else None
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_email(
    email_type: str,
    content: str,
    model: str,
    sender_name: str = "",
    tone: str = "Professionnel",
    mode: str = "generate",
    email_received: str = "",
    reply_type: str = "Réponse neutre",
    job_title: str = "",
    company: str = "",
    profile: str = ""
) -> Dict[str, Any]:
    """
    Génère un email, une réponse à un email, ou une lettre de motivation.
    
    Args:
        email_type: Type d'email (pour mode generate)
        content: Contenu et contexte
        model: Modèle LLM à utiliser
        sender_name: Nom de l'expéditeur
        tone: Ton de l'email
        mode: 'generate' | 'reply' | 'cover_letter'
        email_received: Email reçu (pour mode reply)
        reply_type: Type de réponse (pour mode reply)
        job_title: Poste visé (pour mode cover_letter)
        company: Entreprise (pour mode cover_letter)
        profile: Profil/compétences (pour mode cover_letter)
    """
    client = _get_llm_client()
    
    if mode == "reply":
        system_prompt = get_prompt("email_reply")
        user_prompt_parts = [
            f"Email reçu :\n{email_received}",
            f"\nType de réponse souhaité : {reply_type}",
            f"Ton : {tone}"
        ]
        if content:
            user_prompt_parts.append(f"\nInstructions supplémentaires :\n{content}")
        if sender_name:
            user_prompt_parts.append(f"\nExpéditeur (pour la signature) : {sender_name}")
    elif mode == "cover_letter":
        system_prompt = get_prompt("cover_letter")
        user_prompt_parts = [
            f"Poste visé : {job_title}",
            f"Entreprise : {company}"
        ]
        if profile:
            user_prompt_parts.append(f"\nProfil et compétences :\n{profile}")
        if content:
            user_prompt_parts.append(f"\nInformations complémentaires :\n{content}")
        if sender_name:
            user_prompt_parts.append(f"\nNom du candidat : {sender_name}")
    else:
        system_prompt = get_prompt("email")
        user_prompt_parts = [
            f"Type d'email: {email_type}",
            f"Ton: {tone}",
            f"\nContenu et contexte:\n{content}"
        ]
        if sender_name:
            user_prompt_parts.append(f"\nExpéditeur: {sender_name}")
    
    user_prompt = "\n".join(user_prompt_parts)
    
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            stream=False
        )
        
        result = response.get("message", {}).get("content", "")
        
        _add_to_history({
            "type": "email",
            "input": content or email_received or f"{job_title} - {company}",
            "output": result,
            "options": {
                "email_type": email_type,
                "sender_name": sender_name,
                "tone": tone,
                "mode": mode,
                "reply_type": reply_type if mode == "reply" else None,
                "job_title": job_title if mode == "cover_letter" else None,
                "company": company if mode == "cover_letter" else None
            },
            "model": model
        })
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_prompt(description: str, model: str) -> Dict[str, Any]:
    """
    Génère un prompt IA optimisé.
    
    Args:
        description: Description du besoin
        model: Modèle LLM à utiliser
    
    Returns:
        Dict avec le prompt généré
    """
    client = _get_llm_client()
    system_prompt = get_prompt("prompt")
    
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": description}
            ],
            model=model,
            stream=False
        )
        
        result = response.get("message", {}).get("content", "")
        
        _add_to_history({
            "type": "prompt",
            "input": description,
            "output": result,
            "options": {},
            "model": model
        })
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def extract_data(text: str, model: str, output_format: str = "JSON") -> Dict[str, Any]:
    """
    Extrait des données structurées à partir de texte brut.
    """
    client = _get_llm_client()
    system_prompt = get_prompt("extractor")
    
    user_prompt = f"Format de sortie demandé : {output_format}\n\nTexte à analyser :\n{text}"
    
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            stream=False
        )
        
        result = response.get("message", {}).get("content", "")
        
        _add_to_history({
            "type": "extractor",
            "input": text,
            "output": result,
            "options": {"output_format": output_format},
            "model": model
        })
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def simplify_text(text: str, model: str, level: str = "Grand public") -> Dict[str, Any]:
    """
    Simplifie un texte complexe selon le niveau choisi.
    """
    client = _get_llm_client()
    system_prompt = get_prompt("simplify")
    
    user_prompt = f"Niveau de simplification : {level}\n\nTexte à simplifier :\n{text}"
    
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            stream=False
        )
        
        result = response.get("message", {}).get("content", "")
        
        _add_to_history({
            "type": "simplify",
            "input": text,
            "output": result,
            "options": {"level": level},
            "model": model
        })
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def expand_text(
    text: str,
    model: str,
    tone: str = "Professionnel",
    length: str = "Moyen"
) -> Dict[str, Any]:
    """
    Développe une ébauche en texte complet et articulé.
    """
    client = _get_llm_client()
    system_prompt = get_prompt("expand")
    
    user_prompt = f"Ton : {tone}\nLongueur : {length}\n\nÉbauche à développer :\n{text}"
    
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            stream=False
        )
        
        result = response.get("message", {}).get("content", "")
        
        _add_to_history({
            "type": "expand",
            "input": text,
            "output": result,
            "options": {"tone": tone, "length": length},
            "model": model
        })
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_todolist(text: str, model: str) -> Dict[str, Any]:
    """
    Extrait un plan d'action structuré depuis des notes en vrac.
    """
    client = _get_llm_client()
    system_prompt = get_prompt("todolist")
    
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            model=model,
            stream=False
        )
        
        result = response.get("message", {}).get("content", "")
        
        _add_to_history({
            "type": "todolist",
            "input": text,
            "output": result,
            "options": {},
            "model": model
        })
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_mermaid(
    description: str,
    model: str,
    previous_code: str = "",
    image_base64: str = ""
) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("mermaid")

    user_parts = []

    if previous_code:
        user_parts.append(f"Code Mermaid actuel :\n{previous_code}")
        user_parts.append(f"\nModification demandée :\n{description}")
    else:
        if image_base64:
            user_parts.append("Analyse l'image fournie et génère un diagramme Mermaid qui la représente fidèlement.")
            if description.strip():
                user_parts.append(f"\nInstructions supplémentaires : {description}")
        else:
            user_parts.append(description)

    user_prompt = "\n".join(user_parts)

    images = [image_base64] if image_base64 else None

    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            images=images,
            stream=False
        )

        result = response.get("message", {}).get("content", "")

        result = _clean_mermaid_output(result)

        _add_to_history({
            "type": "mermaid",
            "input": description,
            "output": result,
            "options": {
                "previous_code": previous_code if previous_code else None,
                "has_image": bool(image_base64)
            },
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_documentation(
    outline: str,
    model: str,
    style: str = "Technique",
    previous_doc: str = "",
    improvement_prompt: str = "",
    source_images: list = None,
    embed_images: list = None
) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("documentation")

    source_images = source_images or []
    embed_images = embed_images or []

    user_prompt_parts = []

    if previous_doc and improvement_prompt:
        user_prompt_parts.append(f"Documentation existante :\n{previous_doc}")
        user_prompt_parts.append(f"\nModification demandee :\n{improvement_prompt}")
        if style:
            user_prompt_parts.append(f"\nStyle : {style}")
        # Instruct to preserve image markers during improvement
        if embed_images:
            embed_ids = [img.get('id', f'IMAGE_{i+1}') for i, img in enumerate(embed_images)]
            user_prompt_parts.append(
                f"\nIMPORTANT : La documentation contient des marqueurs d'images ({', '.join(f'[{eid}]' for eid in embed_ids)}). "
                f"Tu DOIS conserver TOUS ces marqueurs dans ta version amelioree, chacun sur sa propre ligne, "
                f"a l'endroit le plus pertinent dans la procedure. Ne supprime aucun marqueur."
            )
    else:
        user_prompt_parts.append(f"Style de documentation : {style}")

        if source_images:
            user_prompt_parts.append(f"\n{len(source_images)} image(s) source(s) fournie(s) pour analyse. Analyse ces images et redige une documentation detaillee basee sur leur contenu.")

        if embed_images:
            embed_ids = [img.get('id', f'IMAGE_{i+1}') for i, img in enumerate(embed_images)]
            user_prompt_parts.append(
                f"\n{len(embed_images)} image(s) a integrer dans la documentation. "
                f"Tu DOIS placer les marqueurs suivants aux endroits pertinents dans le texte : {', '.join(f'[{eid}]' for eid in embed_ids)}. "
                f"Chaque marqueur sera remplace par la capture d'ecran correspondante. "
                f"Place chaque marqueur sur sa propre ligne, au bon endroit dans la procedure."
            )

        if outline.strip():
            label = "Instructions supplementaires" if (source_images or embed_images) else "Trame / plan"
            user_prompt_parts.append(f"\n{label} :\n{outline}")
        elif not source_images and not embed_images:
            user_prompt_parts.append("\nTrame / plan :\n(vide)")

    user_prompt = "\n".join(user_prompt_parts)

    # Combine all images for the LLM (source first, then embed)
    all_images = list(source_images)
    for img in embed_images:
        all_images.append(img.get("base64", ""))
    images_param = all_images if all_images else None

    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=model,
            images=images_param,
            stream=False
        )

        result = response.get("message", {}).get("content", "")

        _add_to_history({
            "type": "documentation",
            "input": outline if not improvement_prompt else improvement_prompt,
            "output": result,
            "options": {
                "style": style,
                "is_improvement": bool(improvement_prompt),
                "original_outline": outline,
                "source_images_count": len(source_images),
                "embed_images_count": len(embed_images)
            },
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def _clean_mermaid_output(raw: str) -> str:
    cleaned = raw.strip()

    if cleaned.startswith("```mermaid"):
        cleaned = cleaned[len("```mermaid"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return cleaned


def generate_summary(text: str, model: str, session_id: str = None) -> Dict[str, Any]:
    """
    Génère un résumé du texte ou des documents RAG.

    
    Args:
        text: Texte à résumer (optionnel si session_id présent)
        model: Modèle LLM à utiliser
        session_id: ID de session RAG (optionnel)
    
    Returns:
        Dict avec le résumé
    """
    client = _get_llm_client()
    system_prompt = get_prompt("summarize")
    
    full_text = text or ""
    
    # Récupérer le contenu RAG si session_id est fourni
    if session_id:
        try:
            # Use absolute import to avoid potential relative import issues if any
            from app.services.rag_service import list_documents, get_document_chunks, init_db
            init_db()
            
            documents = list_documents(session_id)
            current_app.logger.info(f"RAG lookup for session {session_id}: found {len(documents)} documents")
            rag_content = []
            
            for doc in documents:
                current_app.logger.info(f"Processing doc: {doc.get('id')} - {doc.get('filename')} - status: {doc.get('status')}")
                chunks = get_document_chunks(doc['id'])
                current_app.logger.info(f"Got {len(chunks)} chunks for doc {doc.get('id')}")
                # Concaténer les chunks (ils sont triés par index)
                doc_text = " ".join([c['content'] for c in chunks])
                rag_content.append(f"[Document: {doc['filename']}]\n{doc_text}")
                
            if rag_content:
                rag_text = "\n\n".join(rag_content)
                current_app.logger.info(f"Total RAG text length: {len(rag_text)} chars")
                if full_text:
                    full_text = full_text + "\n\n" + rag_text
                else:
                    full_text = rag_text
            else:
                current_app.logger.warning(f"No RAG content found for session {session_id}")
                    
        except Exception as e:
            current_app.logger.error(f"Error retrieving RAG content: {e}")
            import traceback
            current_app.logger.error(traceback.format_exc())
            # On continue avec le texte fourni uniquement s'il y a une erreur
    
    if not full_text.strip():
        return {"success": False, "error": "Aucun texte à résumer (ni texte direct, ni document valide)"}
        
    try:
        response = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_text}
            ],
            model=model,
            stream=False
        )
        
        result = response.get("message", {}).get("content", "")
        
        _add_to_history({
            "type": "summarize",
            "input": text if text else f"[RAG Session: {session_id}]",
            "output": result,
            "options": {"session_id": session_id} if session_id else {},
            "model": model
        })
        
        return {"success": True, "result": result}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_history(filter_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Récupère l'historique des opérations.
    
    Args:
        filter_type: Filtrer par type (optionnel)
        limit: Nombre maximum d'entrées
    
    Returns:
        Liste des entrées de l'historique
    """
    history = _load_history()
    
    if filter_type:
        history = [h for h in history if h.get("type") == filter_type]
    
    return history[:limit]


def get_history_item(item_id: str) -> Optional[Dict[str, Any]]:
    """Récupère un élément spécifique de l'historique."""
    history = _load_history()
    for item in history:
        if item.get("id") == item_id:
            return item
    return None


def clear_history() -> bool:
    """Efface tout l'historique."""
    return _save_history([])


def delete_history_item(item_id: str) -> bool:
    """Supprime un élément de l'historique."""
    history = _load_history()
    new_history = [h for h in history if h.get("id") != item_id]
    if len(new_history) < len(history):
        return _save_history(new_history)
    return False
