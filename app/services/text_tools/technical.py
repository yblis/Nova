from typing import Dict, Any

from ..text_prompts_service import get_prompt
from ._shared import _get_llm_client, _add_to_history


def generate_script(
    description: str,
    model: str,
    language: str = "Bash",
    commented: bool = False,
    strict_mode: bool = False
) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("script_generator")

    user_prompt_parts = []
    user_prompt_parts.append(f"Langage cible : {language}")

    if commented:
        user_prompt_parts.append("Mode commentaires : ACTIVE (ajoute des commentaires detailles)")
    if strict_mode:
        user_prompt_parts.append("Mode strict : ACTIVE (gestion d'erreurs robuste)")

    user_prompt_parts.append(f"\nDescription du script a generer :\n{description}")

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
            "type": "script",
            "input": description,
            "output": result,
            "options": {
                "language": language,
                "commented": commented,
                "strict_mode": strict_mode
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


def generate_regex(text: str, model: str) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("regex_generator")

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
            "type": "regex",
            "input": text,
            "output": result,
            "options": {},
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_prompt(description: str, model: str) -> Dict[str, Any]:
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
