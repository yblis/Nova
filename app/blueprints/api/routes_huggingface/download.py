from flask import jsonify, request, Response
from markupsafe import escape
from . import api_huggingface_bp, hf_client
from ....services.tasks import enqueue_pull_gguf
from ....utils import get_effective_ollama_base_url


@api_huggingface_bp.post("/huggingface/pull")
def pull_gguf() -> Response:
    """Start downloading a GGUF model from HuggingFace"""
    model_id = request.form.get("model_id")
    filename = request.form.get("filename")
    output_dir = request.form.get("output_dir")

    if not model_id or not filename:
        if request.headers.get("HX-Request"):
            return Response(
                "<div class='text-sm text-red-600 dark:text-red-400'>model_id et filename requis</div>",
                mimetype="text/html"
            ), 400
        return jsonify({"error": "model_id et filename requis"}), 400

    try:
        job_id = enqueue_pull_gguf(model_id, filename, output_dir, base_url=get_effective_ollama_base_url())
    except Exception as e:
        if request.headers.get("HX-Request"):
            return Response(
                f"<div class='text-sm text-red-600 dark:text-red-400'>Erreur: {escape(str(e))}</div>",
                mimetype="text/html"
            ), 500
        return jsonify({"error": str(e)}), 500

    html = (
        f"<div class='text-sm mt-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded'>"
        f"<div id='title-{job_id}' class='text-xs'>Téléchargement {escape(filename)}...</div>"
        f"<progress id='bar-{job_id}' max='100' value='0' class='w-full mt-1'></progress>"
        f"<div id='status-{job_id}' class='text-xs text-zinc-500 dark:text-zinc-400 mt-1'></div>"
        f"<script>(function(){{\n"
        f"  var es = new EventSource('/api/stream/progress?job_id={job_id}');\n"
        f"  es.onmessage = function(e){{\n"
        f"    try{{ var d = JSON.parse(e.data); }}catch(_){{ return; }}\n"
        f"    var s=document.getElementById('status-{job_id}');\n"
        f"    var t=document.getElementById('title-{job_id}');\n"
        f"    var b=document.getElementById('bar-{job_id}');\n"
        f"    if(d.progress!=null && b){{ b.value=Math.round(d.progress*100); }}\n"
        f"    if(d.error && s){{ s.textContent=d.error; s.classList.add('text-red-600'); s.classList.add('dark:text-red-400'); }}\n"
        f"    else if(d.status && s){{ s.textContent=d.status; s.classList.remove('text-red-600'); s.classList.remove('dark:text-red-400'); }}\n"
        f"    if(d.done){{\n"
        f"      if(t) t.textContent='✓ Terminé';\n"
        f"      if(b) b.value=100;\n"
        f"      es.close();\n"
        f"    }}\n"
        f"    if(d.error) es.close();\n"
        f"  }};\n"
        f"  es.onerror = function(){{ var s=document.getElementById('status-{job_id}'); if(s) s.textContent='Flux indisponible'; }};\n"
        f"}})();</script>"
        f"</div>"
    )
    return Response(html, mimetype="text/html")


@api_huggingface_bp.get("/huggingface/model/<path:model_id>")
def get_model_info(model_id: str) -> Response:
    """Get detailed information about a specific HuggingFace model"""
    try:
        model = hf_client().get_model_info(model_id)
        return jsonify(model)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_huggingface_bp.get("/huggingface/quantizations")
def get_quantizations() -> Response:
    """Get list of available quantization levels"""
    return jsonify({"quantizations": hf_client().get_available_quantizations()})


@api_huggingface_bp.get("/huggingface/parameter_sizes")
def get_parameter_sizes() -> Response:
    """Get list of common parameter sizes"""
    return jsonify({"parameter_sizes": hf_client().get_available_parameter_sizes()})
