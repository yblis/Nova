import re
from flask import jsonify, request, Response
from markupsafe import escape
from . import api_huggingface_bp, hf_client, _normalize_param_size


@api_huggingface_bp.get("/ollama/search")
def search_ollama() -> Response:
    """Search for models on Ollama.com library"""
    query = (request.args.get("q") or "").strip()
    min_params = request.args.get("min_params", "").strip()
    max_params = request.args.get("max_params", "").strip()
    model_type = request.args.get("model_type", "").strip()

    min_val = None
    max_val = None

    if min_params:
        try:
            min_str = min_params.upper().replace('B', '')
            min_val = float(min_str) if min_str else None
        except (ValueError, TypeError):
            pass

    if max_params:
        try:
            max_str = max_params.upper().replace('B', '')
            parsed = float(max_str) if max_str else None
            if parsed is not None and parsed < 100:
                max_val = parsed
        except (ValueError, TypeError):
            pass

    from ....services.ollama_web import OllamaWebClient, filter_models_by_params, filter_models_by_type

    try:
        results = OllamaWebClient().search_models(query)
        results = filter_models_by_params(results, min_params=min_val, max_params=max_val)
        results = filter_models_by_type(results, model_type=model_type)
    except Exception as e:
        if request.headers.get("HX-Request"):
            return Response(f"<div class='text-red-500'>Error: {str(e)}</div>", mimetype="text/html")
        return jsonify({"error": str(e)}), 500

    if request.headers.get("HX-Request"):
        if not results:
            return Response('''
                <div id="ollama-results" class="grid gap-6 sm:grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 animate-fade-in">
                <div class="col-span-full flex flex-col items-center justify-center py-12 text-zinc-500 dark:text-zinc-400">
                    <svg class="w-12 h-12 mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                    <p>Aucun modèle trouvé dans la librairie Ollama.</p>
                </div>
                </div>
             ''', mimetype="text/html")

        html = ['<div id="ollama-results" class="grid gap-6 sm:grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 animate-fade-in">']
        for model in results:
            name = escape(model.get("name", ""))
            desc = escape(model.get("description", ""))
            param_sizes = model.get("param_sizes", [])
            pull_count = escape(model.get("pull_count", ""))
            capabilities = model.get("capabilities", [])
            safe_model_id = re.sub(r"[^a-zA-Z0-9_-]", "-", str(name))

            size_badges = ""
            if param_sizes:
                badges = []
                for size in param_sizes[:5]:
                    badges.append(f'<span class="bg-brand-50 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase">{escape(size)}</span>')
                if len(param_sizes) > 5:
                    badges.append(f'<span class="text-zinc-400 text-[10px]">+{len(param_sizes) - 5}</span>')
                size_badges = " ".join(badges)

            capability_badges = ""
            cap_colors = {
                "vision": "bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400",
                "tools": "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400",
                "thinking": "bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400",
                "embedding": "bg-cyan-100 dark:bg-cyan-900/30 text-cyan-700 dark:text-cyan-400",
                "code": "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400",
            }
            if capabilities:
                cap_badges = []
                for cap in capabilities:
                    if cap in cap_colors and cap != "cloud":
                        cap_badges.append(f'<span class="{cap_colors[cap]} px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase">{escape(cap)}</span>')
                capability_badges = " ".join(cap_badges)

            html.append(f'''
            <div class="group bg-white dark:bg-zinc-800 rounded-2xl shadow-sm hover:shadow-md border border-zinc-200 dark:border-zinc-700 p-6 flex flex-col gap-4 transition-all">
              <div class="flex items-start justify-between">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-3 mb-2">
                    <div class="w-10 h-10 rounded-lg bg-zinc-100 dark:bg-zinc-700 flex items-center justify-center text-zinc-500 font-bold text-lg flex-shrink-0">
                        {name[:1].upper()}
                    </div>
                    <div class="min-w-0">
                      <h3 class="text-lg font-bold text-zinc-900 dark:text-zinc-100 truncate">{name}</h3>
                      <div class="text-xs text-zinc-500 dark:text-zinc-400 flex items-center flex-wrap gap-2 mt-0.5">
                        <span class="bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded">Library</span>
                        {capability_badges}
                        {f'<span>{pull_count} pulls</span>' if pull_count else ''}
                      </div>
                    </div>
                  </div>
                  <div class="flex flex-wrap gap-1.5 mb-2">{size_badges}</div>
                  <p class="text-xs text-zinc-600 dark:text-zinc-400 line-clamp-2">{desc}</p>
                </div>
                <a href="https://ollama.com/library/{name}" target="_blank" rel="noopener"
                   class="text-zinc-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors p-1"
                   title="Voir sur Ollama">
                    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                </a>
              </div>
              <div class="pt-4 border-t border-zinc-100 dark:border-zinc-700/50">
                <button
                  class="flex items-center gap-2 text-sm font-medium text-brand-600 dark:text-brand-400 hover:text-brand-700 hover:underline transition-colors w-full"
                  hx-get="/api/ollama/model/{name}/tags?min_size={min_val if min_val else 0}&max_size={max_val if max_val else 1000}"
                  hx-target="#sizes-{safe_model_id}"
                  hx-swap="innerHTML"
                  hx-trigger="click once"
                  onclick="document.getElementById('sizes-{safe_model_id}').classList.toggle('hidden')">
                  <svg class="w-4 h-4 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                  Voir les tailles disponibles
                </button>
              <div id="sizes-{safe_model_id}" class="hidden mt-4 space-y-2 max-h-60 overflow-y-auto custom-scrollbar pr-1">
                  <div class="flex items-center justify-center py-4">
                    <svg class="animate-spin h-5 w-5 text-brand-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                    </svg>
                    <span class="ml-2 text-sm text-zinc-500">Chargement des variantes...</span>
                  </div>
                </div>
              </div>
            </div>
            ''')

        html.append('</div>')
        return Response("".join(html), mimetype="text/html")

    return jsonify({"models": results})


@api_huggingface_bp.get("/huggingface/search")
def search_gguf() -> Response:
    """Search for GGUF models on HuggingFace with advanced filters"""
    query = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit", 20))
    sort = request.args.get("sort", "downloads")
    quantization = request.args.get("quantization", "").strip()
    parameter_size = request.args.get("parameter_size", "").strip()
    min_downloads = request.args.get("min_downloads", "").strip()
    min_params = request.args.get("min_params", "").strip()
    max_params = request.args.get("max_params", "").strip()

    filters = {}
    if quantization:
        filters["quantization"] = quantization
    if min_downloads and min_downloads.isdigit():
        filters["min_downloads"] = int(min_downloads)

    if min_params or max_params:
        if min_params:
            filters["min_params"] = _normalize_param_size(min_params)
        if max_params:
            filters["max_params"] = _normalize_param_size(max_params)
        if filters.get("min_params") and filters.get("max_params"):
            try:
                min_v = float(filters["min_params"][:-1])
                max_v = float(filters["max_params"][:-1])
                if min_v > max_v:
                    filters["min_params"], filters["max_params"] = filters["max_params"], filters["min_params"]
            except Exception:
                pass
    elif parameter_size:
        filters["parameter_size"] = parameter_size

    try:
        models = hf_client().search_gguf_models(query=query, limit=limit, sort=sort, filter_params=filters)
    except Exception as e:
        if request.headers.get("HX-Request"):
            return Response(
                f"<div class='col-span-full p-4 bg-red-50 dark:bg-red-900/20 text-red-600 rounded-xl text-sm'>Erreur de recherche: {escape(str(e))}</div>",
                mimetype="text/html"
            )
        return jsonify({"error": str(e)}), 500

    if request.headers.get("Accept") == "application/json" and not request.headers.get("HX-Request"):
        return jsonify({"models": models})

    html = ['<div id="hf-results" class="grid gap-6 sm:grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3">']

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

        if downloads >= 1000000:
            downloads_str = f"{downloads/1000000:.1f}M"
        elif downloads >= 1000:
            downloads_str = f"{downloads/1000:.1f}K"
        else:
            downloads_str = str(downloads)

        html.append(
            f'''
            <div class="group bg-white dark:bg-zinc-800 rounded-2xl shadow-sm hover:shadow-md border border-zinc-200 dark:border-zinc-700 p-6 flex flex-col gap-4 transition-all">
              <div class="flex items-start justify-between">
                <div class="flex-1 min-w-0">
                  <a class="text-lg font-bold text-zinc-900 dark:text-zinc-100 hover:text-brand-600 dark:hover:text-brand-400 transition-colors truncate block"
                     href="https://huggingface.co/{model_id}" target="_blank" rel="noopener">
                    {name}
                  </a>
                  <div class="text-xs font-medium text-zinc-500 dark:text-zinc-400 mt-1">by <span class="text-zinc-700 dark:text-zinc-300">{author}</span></div>
                  <div class="flex flex-wrap gap-3 text-xs text-zinc-500 dark:text-zinc-400 mt-3">
                    <span class="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-700/50 px-2 py-1 rounded">
                        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                        {downloads_str}
                    </span>
                    <span class="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-700/50 px-2 py-1 rounded">
                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd" /></svg>
                        {likes}
                    </span>
                    <span class="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-700/50 px-2 py-1 rounded">
                        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                        {len(gguf_files)} GGUF
                    </span>
                  </div>
                  {f'<p class="text-xs text-zinc-600 dark:text-zinc-400 mt-3 line-clamp-2">{description}...</p>' if description else ''}
                </div>
                <a href="https://huggingface.co/{model_id}" target="_blank" rel="noopener"
                   class="text-zinc-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors p-1"
                   title="Voir sur HuggingFace">
                    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                </a>
              </div>
              <div class="pt-4 border-t border-zinc-100 dark:border-zinc-700/50">
                <button
                  class="flex items-center gap-2 text-sm font-medium text-brand-600 dark:text-brand-400 hover:text-brand-700 hover:underline transition-colors w-full"
                  onclick="document.getElementById('files-{re.sub(r"[^a-zA-Z0-9_-]", "-", str(model_id))}').classList.toggle('hidden')">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
                  Voir les fichiers disponibles
                </button>
              <div id="files-{re.sub(r"[^a-zA-Z0-9_-]", "-", str(model_id))}" class="hidden mt-4 space-y-2 max-h-80 overflow-y-auto custom-scrollbar pr-1">
            '''
        )

        for file in gguf_files[:15]:
            filename = escape(file.get("filename", ""))
            size = file.get("size", 0)
            quantization_level = escape(file.get("quantization", "") or "")
            param_size = escape(file.get("parameter_size", "") or "")

            if size >= 1024 * 1024 * 1024:
                size_str = f"{size / (1024**3):.2f} GB"
            else:
                size_str = f"{size / (1024**2):.1f} MB"

            safe_file_id = re.sub(r"[^a-zA-Z0-9_-]", "-", f"{model_id}-{filename}")
            quant_badge_class = "bg-zinc-100 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300"
            if "Q4_K_M" in quantization_level:
                quant_badge_class = "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 ring-1 ring-green-600/20"
            elif "Q5_K_M" in quantization_level:
                quant_badge_class = "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 ring-1 ring-blue-600/20"

            html.append(
                f'''
                <div class="group/file relative bg-zinc-50 dark:bg-zinc-900/50 hover:bg-white dark:hover:bg-zinc-800 border border-zinc-200 dark:border-zinc-700/50 rounded-xl p-3 flex items-center justify-between gap-3 transition-all hover:shadow-sm">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-xs font-bold text-zinc-700 dark:text-zinc-300 truncate font-mono" title="{filename}">{filename}</span>
                    </div>
                    <div class="flex items-center gap-2 text-[10px] uppercase tracking-wide">
                      <span class="font-medium {quant_badge_class} px-1.5 py-0.5 rounded">{quantization_level or '?'}</span>
                      <span class="text-zinc-400">|</span>
                      <span class="text-zinc-500 font-medium">{size_str}</span>
                      {f'<span class="text-zinc-400">|</span> <span class="text-zinc-500">{param_size}</span>' if param_size else ''}
                    </div>
                  </div>
                  <form hx-post="/api/huggingface/pull" hx-target="#status-{safe_file_id}" class="flex-none">
                    <input type="hidden" name="model_id" value="{model_id}"/>
                    <input type="hidden" name="filename" value="{filename}"/>
                    <button class="flex items-center gap-1.5 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 px-3 py-1.5 rounded-lg text-xs font-bold hover:opacity-90 transition-opacity shadow-sm">
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                      Pull
                    </button>
                  </form>
                </div>
                <div id="status-{safe_file_id}" class="text-xs"></div>
                '''
            )

        html.append('</div></div></div>')

    html.append('</div>')
    return Response("".join(html), mimetype="text/html")
