"""
Routes de téléchargement et statut LM Studio.
"""
from __future__ import annotations

import re
import logging
from flask import jsonify, request, Response
from markupsafe import escape

from . import api_lmstudio_bp, _get_lmstudio_client, _format_size

logger = logging.getLogger(__name__)


@api_lmstudio_bp.post("/lmstudio/download")
def download_lmstudio_model() -> Response:
    """Déclenche le téléchargement d'un modèle via l'API LM Studio."""
    json_data = {}
    try:
        if request.is_json:
            json_data = request.get_json(silent=True) or {}
    except Exception:
        pass

    model = request.form.get("model") or json_data.get("model", "")
    quantization = request.form.get("quantization") or json_data.get("quantization", "")
    filename = request.form.get("filename") or json_data.get("filename", "")

    if not model:
        if request.headers.get("HX-Request"):
            return Response(
                '<div class="text-sm text-red-600 dark:text-red-400">Erreur: modèle non spécifié</div>',
                mimetype="text/html"
            )
        return jsonify({"error": "model requis"}), 400

    if "/" in model and not model.startswith("http"):
        model = f"https://huggingface.co/{model}"
        logger.info(f"Converted model ID to HuggingFace URL: {model}")

    if filename and not quantization:
        quant_match = re.search(r'[._-](Q\d+_[KF]_[MSL]|Q\d+_\d+|Q\d+_K|IQ\d+_[MSL]|F16|F32|BF16)[._-]?', filename, re.IGNORECASE)
        if quant_match:
            quantization = quant_match.group(1).upper()
            logger.info(f"Extracted quantization from filename: {quantization}")

    client = _get_lmstudio_client()
    if not client:
        if request.headers.get("HX-Request"):
            return Response(
                '<div class="text-sm text-red-600 dark:text-red-400">Erreur: LM Studio non configuré. Allez dans Paramètres → Fournisseurs IA.</div>',
                mimetype="text/html"
            )
        return jsonify({"error": "LM Studio non configuré"}), 400

    logger.info(f"Downloading model: {model}, quantization: {quantization}")

    try:
        result = client.download_model_lmstudio(model, quantization)

        if result.get("status") == "already_downloaded":
            if request.headers.get("HX-Request"):
                return Response(
                    '<div class="text-sm text-green-600 dark:text-green-400 flex items-center gap-2">'
                    '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>'
                    'Modèle déjà installé !</div>',
                    mimetype="text/html"
                )
            return jsonify(result)

        job_id = result.get("job_id", "")
        total_size = result.get("total_size_bytes", 0)

        if request.headers.get("HX-Request"):
            safe_job_id = escape(job_id)
            size_str = _format_size(total_size) if total_size else ""

            html = f'''
                <div class="text-sm" x-data="{{progress: 0, status: 'Téléchargement...', done: false, error: null}}" x-init="
                    const es = new EventSource('/api/lmstudio/download/status/{safe_job_id}');
                    es.onmessage = (e) => {{
                        try {{
                            const d = JSON.parse(e.data);
                            if (d.progress != null) progress = Math.round(d.progress * 100);
                            if (d.status) status = d.status;
                            if (d.done) {{ done = true; es.close(); }}
                            if (d.error) {{ error = d.error; es.close(); }}
                        }} catch (_) {{}}
                    }};
                    es.onerror = () => {{ error = 'Connexion perdue'; es.close(); }};
                ">
                    <div x-show="!done && !error" class="space-y-2">
                        <div class="flex justify-between text-xs text-zinc-500">
                            <span x-text="status">Téléchargement...</span>
                            <span>{size_str}</span>
                        </div>
                        <div class="h-2 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden">
                            <div class="h-full bg-teal-500 transition-all duration-300" :style="'width:' + progress + '%'"></div>
                        </div>
                        <div class="text-xs text-zinc-400" x-text="progress + '%'"></div>
                    </div>
                    <div x-show="done" class="text-green-600 dark:text-green-400 flex items-center gap-2">
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
                        Téléchargement terminé !
                    </div>
                    <div x-show="error" class="text-red-600 dark:text-red-400" x-text="'Erreur: ' + error"></div>
                </div>
            '''
            return Response(html, mimetype="text/html")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Download error: {e}")
        if request.headers.get("HX-Request"):
            return Response(
                f'<div class="text-sm text-red-600 dark:text-red-400">Erreur: {escape(str(e))}</div>',
                mimetype="text/html"
            )
        return jsonify({"error": str(e)}), 500


@api_lmstudio_bp.get("/lmstudio/download/status/<job_id>")
def get_download_status(job_id: str) -> Response:
    """Stream SSE pour suivre la progression d'un téléchargement."""
    import time

    client = _get_lmstudio_client()
    if not client:
        return Response(
            f"data: {jsonify({'error': 'LM Studio non configuré'}).get_data(as_text=True)}\n\n",
            mimetype="text/event-stream"
        )

    def generate():
        max_iterations = 600
        for _ in range(max_iterations):
            try:
                status = client.get_download_status_lmstudio(job_id)
                total = status.get("total_size_bytes", 0)
                downloaded = status.get("downloaded_bytes", 0)
                progress = downloaded / total if total > 0 else 0

                status_text = status.get("status", "")
                status_map = {
                    "downloading": "Téléchargement en cours...",
                    "paused": "En pause",
                    "completed": "Terminé !",
                    "failed": "Échec",
                }
                display_status = status_map.get(status_text, status_text)

                speed = status.get("bytes_per_second", 0)
                if speed > 0:
                    speed_str = _format_size(int(speed)) + "/s"
                    display_status = f"{display_status} ({speed_str})"

                event_data = {
                    "progress": progress,
                    "status": display_status,
                    "done": status_text == "completed",
                    "error": status.get("error") if status_text == "failed" else None,
                }
                yield f"data: {jsonify(event_data).get_data(as_text=True)}\n\n"

                if status_text in ("completed", "failed"):
                    break
                time.sleep(1)
            except Exception as e:
                yield f"data: {jsonify({'error': str(e)}).get_data(as_text=True)}\n\n"
                break

    return Response(generate(), mimetype="text/event-stream")


@api_lmstudio_bp.get("/lmstudio/status")
def check_lmstudio_status() -> Response:
    """Vérifie si LM Studio est configuré et accessible."""
    client = _get_lmstudio_client()
    if not client:
        return jsonify({"configured": False, "connected": False, "message": "LM Studio n'est pas configuré"})
    try:
        models = client.list_models()
        return jsonify({"configured": True, "connected": True, "models_count": len(models), "message": f"Connecté - {len(models)} modèle(s) disponible(s)"})
    except Exception as e:
        return jsonify({"configured": True, "connected": False, "message": f"Erreur de connexion: {str(e)}"})
