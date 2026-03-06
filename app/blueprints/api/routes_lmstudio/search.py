"""
Route de recherche LM Studio : combine catalogue GitHub + HuggingFace, rendu HTMX.
"""
from __future__ import annotations

import re
import logging
from flask import jsonify, request, Response
from markupsafe import escape

from . import api_lmstudio_bp
from .catalog import fetch_github_catalog, detect_model_capabilities

logger = logging.getLogger(__name__)


@api_lmstudio_bp.get("/lmstudio/search")
def search_lmstudio_models() -> Response:
    """Recherche les modèles disponibles pour LM Studio."""
    query = (request.args.get("q") or "").strip().lower()
    limit = int(request.args.get("limit", 100))
    sort = request.args.get("sort", "downloads")
    source = request.args.get("source", "all")
    min_params = request.args.get("min_params", "")
    max_params = request.args.get("max_params", "")

    models = []
    seen_ids = set()

    # Source 1: Catalogue GitHub officiel
    if source in ("all", "github"):
        try:
            catalog = fetch_github_catalog()
            for item in catalog:
                name = item.get("name", "")
                model_id = name.lower().replace(" ", "-")
                if query and query not in name.lower() and query not in item.get("description", "").lower():
                    continue
                num_params = item.get("numParameters", "")
                if min_params or max_params:
                    try:
                        param_val = float(num_params.replace("B", "").replace("b", ""))
                        if min_params and param_val < float(min_params):
                            continue
                        if max_params and param_val > float(max_params):
                            continue
                    except (ValueError, TypeError):
                        pass
                if model_id not in seen_ids:
                    seen_ids.add(model_id)
                    files_info = item.get("files", {})
                    all_files = files_info.get("all", [])
                    gguf_files = []
                    for f in all_files:
                        gguf_files.append({
                            "filename": f.get("name", ""),
                            "size": f.get("sizeBytes", 0),
                            "quantization": f.get("quantization", ""),
                            "parameter_size": num_params,
                            "download_url": f.get("url", ""),
                            "repository": f.get("respository", "") or f.get("repository", ""),
                        })
                    gguf_files.sort(key=lambda x: x.get("size", 0), reverse=True)
                    models.append({
                        "id": model_id, "name": name,
                        "author": item.get("author", {}).get("name", "Unknown"),
                        "description": item.get("description", "")[:200],
                        "params": num_params, "source": "github",
                        "downloads": 0, "likes": 0,
                        "download_id": files_info.get("highlighted", {}).get("economical", {}).get("name", ""),
                        "download_url": item.get("resources", {}).get("downloadUrl", ""),
                        "arch": item.get("arch", ""),
                        "gguf_files": gguf_files,
                    })
        except Exception as e:
            logger.warning(f"Error processing GitHub catalog: {e}")

    # Source 2: HuggingFace
    if source in ("all", "huggingface"):
        try:
            from ....services.huggingface_client import HuggingFaceClient
            hf_client = HuggingFaceClient()
            filters = {}
            if min_params:
                filters["min_params"] = min_params
            if max_params:
                filters["max_params"] = max_params
            search_query = query if query else "gguf"
            hf_results = hf_client.search_gguf_models(query=search_query, limit=limit, sort=sort, filter_params=filters)

            for item in hf_results:
                model_id = item.get("id", "")
                name = item.get("name", "")
                if model_id in seen_ids:
                    continue
                seen_ids.add(model_id)
                params = ""
                gguf_files = item.get("gguf_files", [])
                if gguf_files:
                    for f in gguf_files:
                        if f.get("parameter_size"):
                            params = f.get("parameter_size")
                            break
                if not params:
                    for tag in item.get("tags", []):
                        if tag.endswith("B") and tag[:-1].replace(".", "").isdigit():
                            params = tag
                            break
                models.append({
                    "id": model_id, "name": name,
                    "author": item.get("author", "HuggingFace"),
                    "description": item.get("description", ""),
                    "params": params, "source": "huggingface",
                    "downloads": item.get("downloads", 0),
                    "likes": item.get("likes", 0),
                    "download_id": model_id,
                    "full_id_for_detection": model_id,
                    "gguf_files": gguf_files
                })
        except Exception as e:
            logger.warning(f"Error processing HuggingFace models via Client: {e}")

    models.sort(key=lambda x: x.get("downloads", 0), reverse=True)
    models = models[:limit]

    if request.headers.get("Accept") == "application/json" and not request.headers.get("HX-Request"):
        return jsonify({"models": models})

    # HTMX Rendering
    html = ['<div id="lmstudio-results" class="grid gap-6 sm:grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3">']

    if not models:
        html.append('''
            <div class="col-span-full flex flex-col items-center justify-center py-12 text-zinc-500 dark:text-zinc-400">
                <svg class="w-12 h-12 mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <p>Aucun modèle GGUF trouvé pour cette recherche.</p>
            </div>
        ''')

    for model in models:
        model_id = escape(model.get("id", ""))
        author = escape(model.get("author", ""))
        name = escape(model.get("name", ""))
        downloads = model.get("downloads", 0)
        likes = model.get("likes", 0)
        gguf_files = model.get("gguf_files", [])
        description = escape(model.get("description", "")[:150])

        param_sizes = []
        seen_sizes = set()
        for f in gguf_files:
            ps = f.get("parameter_size", "")
            if ps and ps not in seen_sizes:
                param_sizes.append(ps)
                seen_sizes.add(ps)

        size_badges = ""
        if param_sizes:
            badges = []
            for size in param_sizes[:5]:
                badges.append(f'<span class="bg-brand-50 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase">{escape(size)}</span>')
            if len(param_sizes) > 5:
                badges.append(f'<span class="text-zinc-400 text-[10px]">+{len(param_sizes) - 5}</span>')
            size_badges = " ".join(badges)

        if downloads >= 1000000:
            downloads_str = f"{downloads/1000000:.1f}M"
        elif downloads >= 1000:
            downloads_str = f"{downloads/1000:.1f}K"
        else:
            downloads_str = str(downloads)

        safe_model_id = "lms-" + re.sub(r"[^a-zA-Z0-9_-]", "-", str(model_id))

        # Build files section
        files_section_html = ""
        if gguf_files:
            files_items = []
            for file in gguf_files[:15]:
                fn = escape(file.get("filename", ""))
                sz = file.get("size", 0)
                qt = escape(file.get("quantization", "") or "")
                ps = escape(file.get("parameter_size", "") or "")
                repo = file.get("repository", "") or model_id

                if sz >= 1024 * 1024 * 1024:
                    sz_str = f"{sz / (1024**3):.2f} GB"
                elif sz > 0:
                    sz_str = f"{sz / (1024**2):.1f} MB"
                else:
                    sz_str = "? MB"

                safe_fid = re.sub(r"[^a-zA-Z0-9_-]", "-", f"{model_id}-{fn}")
                qc = "bg-zinc-100 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300"
                if "Q4_K_M" in qt:
                    qc = "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                elif "Q5_K_M" in qt:
                    qc = "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"

                files_items.append(f'''
                    <div class="bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-700/50 rounded-xl p-3 flex items-center justify-between gap-3">
                      <div class="flex-1 min-w-0">
                        <div class="text-xs font-bold text-zinc-700 dark:text-zinc-300 truncate font-mono mb-1">{fn}</div>
                        <div class="flex items-center gap-2 text-[10px]">
                          <span class="{qc} px-1.5 py-0.5 rounded font-medium">{qt or '?'}</span>
                          <span class="text-zinc-500">{sz_str}</span>
                          {f'<span class="text-zinc-500">{ps}</span>' if ps else ''}
                        </div>
                      </div>
                      <form hx-post="/api/lmstudio/download" hx-target="#st-{safe_fid}" class="flex-none">
                        <input type="hidden" name="model" value="{escape(repo)}"/>
                        <input type="hidden" name="filename" value="{fn}"/>
                        <button class="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 px-3 py-1.5 rounded-lg text-xs font-bold">Pull</button>
                      </form>
                    </div>
                    <div id="st-{safe_fid}" class="text-xs"></div>
                ''')

            files_section_html = f'''
                <button class="flex items-center gap-2 text-sm font-medium text-brand-600 dark:text-brand-400 hover:underline w-full"
                        onclick="document.getElementById('files-{safe_model_id}').classList.toggle('hidden')">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                  Voir les {len(gguf_files)} fichiers
                </button>
                <div id="files-{safe_model_id}" class="hidden mt-4 space-y-2 max-h-80 overflow-y-auto">
                  {"".join(files_items)}
                </div>
            '''
        else:
            files_section_html = '<div class="text-sm text-zinc-500 py-2">Aucun fichier GGUF détecté</div>'

        html.append(f'''
            <div class="group bg-white dark:bg-zinc-800 rounded-2xl shadow-sm hover:shadow-md border border-zinc-200 dark:border-zinc-700 p-6 flex flex-col gap-4 transition-all">
              <div class="flex items-start justify-between">
                <div class="flex-1 min-w-0">
                  <a class="text-lg font-bold text-zinc-900 dark:text-zinc-100 hover:text-brand-600 transition-colors truncate block"
                     href="https://huggingface.co/{model_id}" target="_blank">{name}</a>
                  <div class="text-xs text-zinc-500 mt-1">by <span class="text-zinc-700 dark:text-zinc-300">{author}</span></div>
                  <div class="flex flex-wrap gap-1.5 mt-2 mb-2">{size_badges}</div>
                  <div class="flex flex-wrap gap-3 text-xs text-zinc-500 mt-2">
                    <span class="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-700/50 px-2 py-1 rounded">
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                      {downloads_str}
                    </span>
                    <span class="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-700/50 px-2 py-1 rounded">
                      <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z"/></svg>
                      {likes}
                    </span>
                    <span class="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-700/50 px-2 py-1 rounded">{len(gguf_files)} GGUF</span>
                  </div>
                  {f'<p class="text-xs text-zinc-600 dark:text-zinc-400 mt-3 line-clamp-2">{description}...</p>' if description else ''}
                </div>
                <a href="https://huggingface.co/{model_id}" target="_blank" class="text-zinc-400 hover:text-brand-600 p-1">
                  <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                </a>
              </div>
              <div class="pt-4 border-t border-zinc-100 dark:border-zinc-700/50">
                {files_section_html}
              </div>
            </div>
        ''')

    html.append('</div>')
    return Response("".join(html), mimetype="text/html")
