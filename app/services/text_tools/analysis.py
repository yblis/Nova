from typing import Dict, Any, Optional

from ..text_prompts_service import get_prompt
from ._shared import _get_llm_client, _add_to_history


def extract_data(text: str, model: str, output_format: str = "JSON") -> Dict[str, Any]:
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


def compare_decide(text: str, model: str) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("decision")

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
            "type": "decision",
            "input": text,
            "output": result,
            "options": {},
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def explain_eli5(
    text: str,
    model: str,
    level: str = "Grand public"
) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("eli5")

    user_prompt = f"Niveau d'explication : {level}\n\nConcept a expliquer :\n{text}"

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
            "type": "eli5",
            "input": text,
            "output": result,
            "options": {"level": level},
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_summary(text: str, model: str, session_id: str = None) -> Dict[str, Any]:
    from flask import current_app
    client = _get_llm_client()
    system_prompt = get_prompt("summarize")

    full_text = text or ""

    if session_id:
        try:
            from app.services.rag_service import list_documents, get_document_chunks, init_db
            init_db()

            documents = list_documents(session_id)
            current_app.logger.info(f"RAG lookup for session {session_id}: found {len(documents)} documents")
            rag_content = []

            for doc in documents:
                current_app.logger.info(f"Processing doc: {doc.get('id')} - {doc.get('filename')} - status: {doc.get('status')}")
                chunks = get_document_chunks(doc['id'])
                current_app.logger.info(f"Got {len(chunks)} chunks for doc {doc.get('id')}")
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


def convert_format(
    text: str,
    model: str,
    target_format: str = "JSON"
) -> Dict[str, Any]:
    client = _get_llm_client()
    system_prompt = get_prompt("format_converter")

    user_prompt = f"Format cible : {target_format}\n\nDonnees source :\n{text}"

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
            "type": "converter",
            "input": text,
            "output": result,
            "options": {"target_format": target_format},
            "model": model
        })

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}
