from typing import Dict, Any, List, Optional

from ..text_prompts_service import get_prompt
from ._shared import _get_llm_client, _add_to_history


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
    client = _get_llm_client()

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
    client = _get_llm_client()
    system_prompt = get_prompt("correction")

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


def expand_text(
    text: str,
    model: str,
    tone: str = "Professionnel",
    length: str = "Moyen"
) -> Dict[str, Any]:
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
