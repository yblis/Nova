import re
from flask import jsonify, request, Response
from markupsafe import escape
from . import api_huggingface_bp


@api_huggingface_bp.get("/ollama/model/<path:model_name>/tags")
def get_ollama_model_tags(model_name: str) -> Response:
    """Get all tags/variants for a specific Ollama model"""
    from ....services.ollama_web import OllamaWebClient

    min_size_gb = request.args.get("min_size", "").strip()
    max_size_gb = request.args.get("max_size", "").strip()

    min_size = None
    max_size = None
    if min_size_gb:
        try:
            min_size = float(min_size_gb)
        except (ValueError, TypeError):
            pass
    if max_size_gb:
        try:
            val = float(max_size_gb)
            if val < 100:
                max_size = val
        except (ValueError, TypeError):
            pass

    try:
        tags = OllamaWebClient(timeout=15.0).get_model_tags(model_name)
    except Exception as e:
        if request.headers.get("HX-Request"):
            return Response(f"<div class='text-red-500 text-xs'>Erreur: {escape(str(e))}</div>", mimetype="text/html")
        return jsonify({"error": str(e)}), 500

    # Filter by size
    if min_size is not None or max_size is not None:
        filtered_tags = []
        for tag in tags:
            size_str = tag.get("size", "")
            if not size_str:
                continue
            size_match = re.match(r'([\d.]+)\s*(GB|MB|KB)?', size_str, re.IGNORECASE)
            if not size_match:
                continue
            try:
                size_val = float(size_match.group(1))
                unit = (size_match.group(2) or "GB").upper()
                if unit == "MB":
                    size_val = size_val / 1024
                elif unit == "KB":
                    size_val = size_val / (1024 * 1024)
                if min_size is not None and size_val < min_size:
                    continue
                if max_size is not None and size_val > max_size:
                    continue
                filtered_tags.append(tag)
            except (ValueError, TypeError):
                continue
        tags = filtered_tags

    if not request.headers.get("HX-Request"):
        return jsonify({"model": model_name, "tags": tags})

    if not tags:
        return Response(
            f'''<div class="text-sm text-zinc-500 dark:text-zinc-400 py-2">
                Aucune variante trouvée.
                <button class="flex items-center gap-1.5 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 px-3 py-1.5 rounded-lg text-xs font-bold mt-2"
                        hx-post="/api/models/pull"
                        hx-vals='{{"name": "{escape(model_name)}"}}'>
                    Pull {escape(model_name)}:latest
                </button>
            </div>''',
            mimetype="text/html"
        )

    html = []
    for tag in tags[:20]:
        tag_name = escape(tag.get("tag", ""))
        full_name = escape(tag.get("full_name", f"{model_name}:{tag_name}"))
        size = escape(tag.get("size", ""))
        context = escape(tag.get("context", ""))
        input_type = escape(tag.get("input_type", ""))
        safe_tag_id = re.sub(r"[^a-zA-Z0-9_-]", "-", full_name)

        input_badge = ""
        if "Image" in input_type or "Video" in input_type:
            input_badge = f'<span class="bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 px-1.5 py-0.5 rounded text-[9px] uppercase">Vision</span>'

        html.append(f'''
        <div class="group/size relative bg-zinc-50 dark:bg-zinc-900/50 hover:bg-white dark:hover:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/50 rounded-xl p-3 flex items-center justify-between gap-3 transition-all hover:shadow-sm">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-bold text-zinc-700 dark:text-zinc-300">{full_name}</span>
            </div>
            <div class="flex items-center flex-wrap gap-2 text-[10px] uppercase tracking-wide mt-1.5">
              {f'<span class="font-semibold bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-1.5 py-0.5 rounded">{size}</span>' if size else ''}
              {f'<span class="text-zinc-400">•</span><span class="text-zinc-500 font-medium">{context} ctx</span>' if context else ''}
              {input_badge}
            </div>
          </div>
          <button class="flex items-center gap-1.5 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 px-3 py-1.5 rounded-lg text-xs font-bold hover:opacity-90 transition-opacity shadow-sm"
                  hx-post="/api/models/pull"
                  hx-vals='{{"name": "{full_name}"}}'
                  hx-target="#status-ollama-{safe_tag_id}"
                  hx-swap="innerHTML">
            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
            Pull
          </button>
        </div>
        <div id="status-ollama-{safe_tag_id}" class="text-xs"></div>
        ''')

    return Response("".join(html), mimetype="text/html")
