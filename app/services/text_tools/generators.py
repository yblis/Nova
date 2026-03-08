from typing import Dict, Any

from ..text_prompts_service import get_prompt
from ._shared import _get_llm_client, _add_to_history


def generate_documentation(
    outline: str,
    model: str,
    style: str = "Technique",
    previous_doc: str = "",
    improvement_prompt: str = "",
    source_images: list = None,
    embed_images: list = None
) -> Dict[str, Any]:
    client = _get_llm_client(model)
    system_prompt = get_prompt("documentation")

    source_images = source_images or []
    embed_images = embed_images or []

    user_prompt_parts = []

    if previous_doc and improvement_prompt:
        user_prompt_parts.append(f"Documentation existante :\n{previous_doc}")
        user_prompt_parts.append(f"\nModification demandee :\n{improvement_prompt}")
        if style:
            user_prompt_parts.append(f"\nStyle : {style}")
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


def generate_todolist(text: str, model: str) -> Dict[str, Any]:
    client = _get_llm_client(model)
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


def generate_flashcards(
    text: str,
    model: str,
    difficulty: str = "Intermédiaire",
    card_format: str = "Question/Réponse"
) -> Dict[str, Any]:
    client = _get_llm_client(model)
    system_prompt = get_prompt("flashcards")

    user_prompt = f"Niveau de difficulte : {difficulty}\nFormat : {card_format}\n\nContenu source :\n{text}"

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
            "type": "flashcards",
            "input": text,
            "output": result,
            "options": {"difficulty": difficulty, "card_format": card_format},
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}
