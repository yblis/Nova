from typing import Dict, Any

from ..text_prompts_service import get_prompt
from ._shared import _get_llm_client, _add_to_history


def generate_recipe(
    text: str,
    model: str,
    diet: str = "",
    time: str = "",
    servings: str = ""
) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("recipe")

    user_parts = []
    if diet and diet != "Sans restriction":
        user_parts.append(f"Regime alimentaire : {diet}")
    if time:
        user_parts.append(f"Temps maximum : {time}")
    if servings:
        user_parts.append(f"Nombre de portions : {servings}")
    user_parts.append(f"\n{text}")

    user_prompt = "\n".join(user_parts)

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
            "type": "recipe",
            "input": text,
            "output": result,
            "options": {"diet": diet, "time": time, "servings": servings},
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_fitness(
    text: str,
    model: str,
    goal: str = "",
    equipment: str = "",
    level: str = ""
) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("fitness")

    user_parts = []
    if goal:
        user_parts.append(f"Objectif : {goal}")
    if equipment:
        user_parts.append(f"Materiel disponible : {equipment}")
    if level:
        user_parts.append(f"Niveau : {level}")
    user_parts.append(f"\n{text}")

    user_prompt = "\n".join(user_parts)

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
            "type": "fitness",
            "input": text,
            "output": result,
            "options": {"goal": goal, "equipment": equipment, "level": level},
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_admin_letter(
    text: str,
    model: str,
    letter_type: str = ""
) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("admin_letter")

    user_parts = []
    if letter_type:
        user_parts.append(f"Type de lettre : {letter_type}")
    user_parts.append(f"\nSituation a decrire :\n{text}")

    user_prompt = "\n".join(user_parts)

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
            "type": "admin_letter",
            "input": text,
            "output": result,
            "options": {"letter_type": letter_type},
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_speech(
    text: str,
    model: str,
    occasion: str = "",
    tone: str = ""
) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("speech")

    user_parts = []
    if occasion:
        user_parts.append(f"Occasion : {occasion}")
    if tone:
        user_parts.append(f"Ton souhaite : {tone}")
    user_parts.append(f"\nContexte et points cles :\n{text}")

    user_prompt = "\n".join(user_parts)

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
            "type": "speech",
            "input": text,
            "output": result,
            "options": {"occasion": occasion, "tone": tone},
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}
