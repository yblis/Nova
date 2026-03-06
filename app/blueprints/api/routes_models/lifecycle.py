import json
from flask import request, current_app, Response, jsonify
from markupsafe import escape
from . import api_models_bp, client
from ....services.tasks import enqueue_pull_model, enqueue_check_update, enqueue_eject_force
from ....utils import get_effective_ollama_base_url
from ....services.model_metadata_service import delete_model_metadata


@api_models_bp.post("/models/pull")
def pull_model() -> Response:
    name = request.values.get("name") or (request.json or {}).get("name")
    if not name:
        return jsonify({"error": "name requis"}), 400
    job_id = enqueue_pull_model(name, base_url=get_effective_ollama_base_url())
    html = (
        f"<div class='text-sm'>"
        f"<div>Pull {escape(name)}…</div>"
        f"<progress id='bar-{job_id}' max='100' value='0' class='w-full'></progress>"
        f"<div id='status-{job_id}' class='text-xs text-slate-500 mt-1'></div>"
        f"<script>(function(){{\n"
        f"  var es = new EventSource('/api/stream/progress?job_id={job_id}');\n"
        f"  es.onmessage = function(e){{\n"
        f"    try{{ var d = JSON.parse(e.data); }}catch(_){{ return; }}\n"
        f"    if(d.progress!=null){{ var p=document.getElementById('bar-{job_id}'); if(p) p.value=Math.round(d.progress*100); }}\n"
        f"    var s=document.getElementById('status-{job_id}');\n"
        f"    if(d.error && s){{ s.textContent='Erreur: '+d.error; s.className='text-xs text-red-600 mt-1'; }}\n"
        f"    else if(d.status && s){{ s.textContent=d.status; }}\n"
        f"    if(d.done){{ var p=document.getElementById('bar-{job_id}'); if(p) p.value=100; }}\n"
        f"    if(d.done||d.error) es.close();\n"
        f"  }};\n"
        f"  es.onerror = function(){{ var s=document.getElementById('status-{job_id}'); if(s) s.textContent='Flux indisponible'; }};\n"
        f"}})();</script>"
        f"</div>"
    )
    return Response(html, mimetype="text/html")


@api_models_bp.delete("/models/<name>")
def delete_model(name: str) -> Response:
    try:
        ok = client().delete(name)
        if ok:
            delete_model_metadata(name)
        if request.headers.get("HX-Request"):
            msg = f"Modèle {escape(name)} supprimé" if ok else f"Échec suppression de {escape(name)}"
            color = "text-green-600 dark:text-green-400" if ok else "text-red-600 dark:text-red-400"
            return Response(
                f"<div id='action-out' class='text-sm {color}'>{msg}</div>",
                mimetype="text/html"
            )
        return jsonify({"deleted": ok})
    except Exception as e:
        if request.headers.get("HX-Request"):
            return Response(
                f"<div id='action-out' class='text-sm text-red-600 dark:text-red-400'>Erreur: {escape(str(e))}</div>",
                mimetype="text/html"
            )
        return jsonify({"error": str(e)}), 500


@api_models_bp.post("/models/unload")
def unload_model() -> Response:
    """Décharge un modèle LM Studio de la mémoire. Requiert LM Studio 0.4.0+."""
    model_name = request.values.get("model") or (request.get_json(silent=True) or {}).get("model", "")

    if not model_name:
        if request.headers.get("HX-Request"):
            return Response('<div class="ds-toast ds-toast-error">Nom du modèle requis</div>', mimetype="text/html")
        return jsonify({"error": "model name required"}), 400

    try:
        from ....services.provider_manager import get_provider_manager
        from ....services.llm_clients.openai_compatible_client import OpenAICompatibleClient

        mgr = get_provider_manager()
        providers = mgr.get_providers()
        lm_provider = None
        for provider in providers:
            if provider.get("type") == "lmstudio":
                full_provider = mgr.get_provider(provider["id"], include_api_key=True)
                if full_provider and full_provider.get("url"):
                    lm_provider = full_provider
                    break

        if not lm_provider:
            if request.headers.get("HX-Request"):
                return Response('<div class="ds-toast ds-toast-error">Aucun provider LM Studio configuré</div>', mimetype="text/html")
            return jsonify({"error": "No LM Studio provider configured"}), 400

        lm_client = OpenAICompatibleClient(
            provider_type="lmstudio",
            base_url=lm_provider.get("url"),
            api_key=lm_provider.get("api_key", "")
        )

        loaded_models = lm_client.list_loaded_models()
        instance_id = None
        for m in loaded_models:
            if m.get("id") == model_name or m.get("name") == model_name:
                instance_id = m.get("instance_id")
                break

        if not instance_id:
            if request.headers.get("HX-Request"):
                return Response(
                    f'<div class="ds-toast ds-toast-warning">Modèle {escape(model_name)} non trouvé en mémoire</div>',
                    mimetype="text/html"
                )
            return jsonify({"error": f"Model {model_name} not loaded"}), 404

        result = lm_client.unload_model_lmstudio(instance_id)

        if request.headers.get("HX-Request"):
            hx_target = request.headers.get("HX-Target", "")
            if hx_target == "running":
                from .monitoring import running
                return running()
            return Response(
                f'<div class="ds-toast ds-toast-success">Modèle {escape(model_name)} déchargé</div>',
                mimetype="text/html"
            )
        return jsonify({"unloaded": True, "instance_id": instance_id, **result})

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to unload model {model_name}: {e}")
        if request.headers.get("HX-Request"):
            return Response(
                f'<div class="ds-toast ds-toast-error">Erreur: {escape(str(e))}</div>',
                mimetype="text/html"
            )
        return jsonify({"error": str(e)}), 500


@api_models_bp.post("/models/create")
def create_model() -> Response:
    """Create a custom model based on an existing model with modified parameters."""
    data = request.get_json() or {}
    name = data.get("name")
    from_model = data.get("from_model")
    system = data.get("system")
    template = data.get("template")
    parameters = data.get("parameters")

    if not name or not from_model:
        return jsonify({"error": "name et from_model requis"}), 400

    accept = request.headers.get("Accept", "")
    want_sse = "text/event-stream" in accept
    ollama = client()

    def generate_sse():
        try:
            for chunk in ollama.create_model(
                name=name, from_model=from_model, system=system,
                template=template, parameters=parameters
            ):
                if "error" in chunk:
                    yield f"data: {json.dumps({'error': chunk['error']})}\n\n"
                    return
                yield f"data: {json.dumps(chunk)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f'data: {{"status": "Erreur", "error": "{escape(str(e))}", "done": true}}\n\n'

    if want_sse:
        return Response(generate_sse(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    try:
        result = None
        for evt in client().create_model(
            name=name, from_model=from_model, system=system,
            template=template, parameters=parameters
        ):
            result = evt
            if evt.get("error"):
                return jsonify({"error": evt["error"]}), 500
        return jsonify({"success": True, "model": name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_models_bp.post("/models/copy")
def copy_model() -> Response:
    source = request.values.get("source") or (request.json or {}).get("source")
    dest = request.values.get("dest") or (request.json or {}).get("dest")
    if not source or not dest:
        if request.headers.get("HX-Request"):
            return Response(
                "<div id='action-out' class='text-sm text-red-600 dark:text-red-400'>Source et destination requis</div>",
                mimetype="text/html"
            ), 400
        return jsonify({"error": "source et dest requis"}), 400
    try:
        ok = client().copy(source, dest)
        if request.headers.get("HX-Request"):
            msg = f"Copie {escape(source)} → {escape(dest)} réussie" if ok else "Échec copie"
            color = "text-green-600 dark:text-green-400" if ok else "text-red-600 dark:text-red-400"
            return Response(f"<div id='action-out' class='text-sm {color}'>{msg}</div>", mimetype="text/html")
        return jsonify({"copied": ok})
    except Exception as e:
        if request.headers.get("HX-Request"):
            return Response(
                f"<div id='action-out' class='text-sm text-red-600 dark:text-red-400'>Erreur: {escape(str(e))}</div>",
                mimetype="text/html"
            )
        return jsonify({"error": str(e)}), 500


@api_models_bp.post("/eject")
def eject() -> Response:
    name = request.values.get("name") or (request.json or {}).get("name")
    if not name:
        return jsonify({"error": "name requis"}), 400
    try:
        client().generate(prompt="", keep_alive=0, stream=False, model=name)
    except Exception:
        pass
    from .monitoring import running
    return running()


@api_models_bp.post("/eject/force")
def eject_force() -> Response:
    job_id = enqueue_eject_force(base_url=get_effective_ollama_base_url())
    return jsonify({"job_id": job_id})


@api_models_bp.post("/models/check_update")
def check_update() -> Response:
    name = request.values.get("name") or (request.json or {}).get("name")
    if not name:
        return jsonify({"error": "name requis"}), 400
    job_id = enqueue_check_update(name, base_url=get_effective_ollama_base_url())
    return jsonify({"job_id": job_id})
