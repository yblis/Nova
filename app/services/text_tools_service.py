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
    length: str = "Moyen"
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
    system_prompt = get_prompt("reformulation")
    
    # Construire le user prompt avec les options
    user_prompt_parts = [f"Texte à reformuler:\n{text}"]
    
    if context:
        user_prompt_parts.append(f"\nContexte: {context}")
    
    user_prompt_parts.append(f"\nTon demandé: {tone}")
    user_prompt_parts.append(f"Format: {format_type}")
    user_prompt_parts.append(f"Longueur: {length}")
    
    if add_emojis:
        user_prompt_parts.append("\nAjoute des emojis pertinents dans le texte reformulé.")
    
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
            "type": "reformulation",
            "input": text,
            "output": result,
            "options": {
                "context": context,
                "add_emojis": add_emojis,
                "tone": tone,
                "format": format_type,
                "length": length
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
    tone: str = "Professionnel"
) -> Dict[str, Any]:
    """
    Génère un email structuré.
    
    Args:
        email_type: Type d'email (réclamation, demande de congés, etc.)
        content: Contenu et contexte
        model: Modèle LLM à utiliser
        sender_name: Nom de l'expéditeur (optionnel)
        tone: Ton de l'email
    
    Returns:
        Dict avec l'email généré
    """
    client = _get_llm_client()
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
            "input": content,
            "output": result,
            "options": {
                "email_type": email_type,
                "sender_name": sender_name,
                "tone": tone
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
