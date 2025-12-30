"""
API routes for HuggingFace model search and download
"""
from __future__ import annotations

import re
from flask import Blueprint, jsonify, request, current_app, Response
from markupsafe import escape

from ...services.huggingface_client import HuggingFaceClient
from ...services.tasks import enqueue_pull_gguf
from ...utils import get_effective_ollama_base_url


api_huggingface_bp = Blueprint("api_huggingface", __name__)


def hf_client() -> HuggingFaceClient:
    return HuggingFaceClient(
        hf_token=current_app.config.get("HF_TOKEN"),
        connect_timeout=current_app.config["HTTP_CONNECT_TIMEOUT"],
        read_timeout=current_app.config["HTTP_READ_TIMEOUT"],
    )



@api_huggingface_bp.get("/ollama/search")
def search_ollama() -> Response:
    """
    Search for models on Ollama.com library
    """
    query = (request.args.get("q") or "").strip()
    
    # Filtering Logic for Ollama
    min_params = request.args.get("min_params", "").strip()
    max_params = request.args.get("max_params", "").strip()
    model_type = request.args.get("model_type", "").strip()
    
    # Parse filter bounds
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
            # If max is 100 or more, treat as "no max limit"
            parsed = float(max_str) if max_str else None
            if parsed is not None and parsed < 100:
                max_val = parsed
        except (ValueError, TypeError):
            pass

    print(f"DEBUG: Ollama Search Query: '{query}', min_params: {min_val}, max_params: {max_val}, type: {model_type}")

    # Import locally to avoid circular imports if any
    from ...services.ollama_web import OllamaWebClient, filter_models_by_params, filter_models_by_type
    
    try:
        results = OllamaWebClient().search_models(query)
        print(f"DEBUG: Ollama Search Results (before filter): {len(results)} items")
        
        # Apply parameter size filtering
        results = filter_models_by_params(results, min_params=min_val, max_params=max_val)
        print(f"DEBUG: Ollama Search Results (after param filter): {len(results)} items")
        
        # Apply type filtering
        results = filter_models_by_type(results, model_type=model_type)
        print(f"DEBUG: Ollama Search Results (after type filter): {len(results)} items")
        
    except Exception as e:
        print(f"DEBUG: Ollama Search Error: {e}")
        if request.headers.get("HX-Request"):
             return Response(f"<div class='text-red-500'>Error: {str(e)}</div>", mimetype="text/html")
        return jsonify({"error": str(e)}), 500

    # HTMX Rendering
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
            
            # Create safe ID for DOM elements
            safe_model_id = re.sub(r"[^a-zA-Z0-9_-]", "-", str(name))
            
            # Build parameter size badges for header
            size_badges = ""
            if param_sizes:
                badges = []
                for size in param_sizes[:5]:  # Limit to 5 sizes in header
                    badges.append(f'<span class="bg-brand-50 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase">{escape(size)}</span>')
                if len(param_sizes) > 5:
                    badges.append(f'<span class="text-zinc-400 text-[10px]">+{len(param_sizes) - 5}</span>')
                size_badges = " ".join(badges)
            
            # Build capability badges
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
                    if cap in cap_colors and cap != "cloud":  # Skip 'cloud' as it's not relevant
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
                  
                  <div class="flex flex-wrap gap-1.5 mb-2">
                    {size_badges}
                  </div>
                  
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


@api_huggingface_bp.get("/ollama/model/<path:model_name>/tags")
def get_ollama_model_tags(model_name: str) -> Response:
    """
    Get all tags/variants for a specific Ollama model with size, context, and input type
    Optionally filter by size range (min_size, max_size in billions of parameters)
    Returns HTML for HTMX or JSON
    """
    from ...services.ollama_web import OllamaWebClient
    
    # Get size filter parameters (in GB)
    min_size_gb = request.args.get("min_size", "").strip()
    max_size_gb = request.args.get("max_size", "").strip()
    
    # Parse size filters
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
            # Only apply max if it's less than 100 (to avoid filtering out large models when slider is at max)
            if val < 100:
                max_size = val
        except (ValueError, TypeError):
            pass
    
    try:
        tags = OllamaWebClient(timeout=15.0).get_model_tags(model_name)
    except Exception as e:
        print(f"DEBUG: Error fetching Ollama model tags: {e}")
        if request.headers.get("HX-Request"):
            return Response(
                f"<div class='text-red-500 text-xs'>Erreur: {escape(str(e))}</div>",
                mimetype="text/html"
            )
        return jsonify({"error": str(e)}), 500

    # Filter tags by size if parameters are provided
    if min_size is not None or max_size is not None:
        filtered_tags = []
        for tag in tags:
            size_str = tag.get("size", "")
            if not size_str:
                continue  # Skip tags without size info
            
            # Parse size (e.g., "6.1GB", "1.9GB", "143GB")
            size_match = re.match(r'([\d.]+)\s*(GB|MB|KB)?', size_str, re.IGNORECASE)
            if not size_match:
                continue
            
            try:
                size_val = float(size_match.group(1))
                unit = (size_match.group(2) or "GB").upper()
                
                # Convert to GB for comparison
                if unit == "MB":
                    size_val = size_val / 1024
                elif unit == "KB":
                    size_val = size_val / (1024 * 1024)
                
                # Check if size is in range
                if min_size is not None and size_val < min_size:
                    continue
                if max_size is not None and size_val > max_size:
                    continue
                
                filtered_tags.append(tag)
            except (ValueError, TypeError):
                continue
        
        tags = filtered_tags

    # Return JSON if not HTMX
    if not request.headers.get("HX-Request"):
        return jsonify({"model": model_name, "tags": tags})

    # HTMX Rendering - return list of variants with sizes
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
    for tag in tags[:20]:  # Limit to 20 variants
        tag_name = escape(tag.get("tag", ""))
        full_name = escape(tag.get("full_name", f"{model_name}:{tag_name}"))
        size = escape(tag.get("size", ""))
        context = escape(tag.get("context", ""))
        input_type = escape(tag.get("input_type", ""))
        
        safe_tag_id = re.sub(r"[^a-zA-Z0-9_-]", "-", full_name)
        
        # Badge for input type
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


@api_huggingface_bp.get("/huggingface/search")
def search_gguf() -> Response:
    """
    Search for GGUF models on HuggingFace with advanced filters
    Returns HTML for HTMX or JSON
    """
    # Get search parameters
    query = (request.args.get("q") or "").strip()
    limit = int(request.args.get("limit", 20))
    sort = request.args.get("sort", "downloads")
    quantization = request.args.get("quantization", "").strip()
    parameter_size = request.args.get("parameter_size", "").strip()
    min_downloads = request.args.get("min_downloads", "").strip()
    min_params = request.args.get("min_params", "").strip()
    max_params = request.args.get("max_params", "").strip()

    # Build filters
    filters = {}
    if quantization:
        filters["quantization"] = quantization
    if min_downloads and min_downloads.isdigit():
        filters["min_downloads"] = int(min_downloads)
    
    # Handle parameter size filters - range takes priority over exact
    if min_params or max_params:
        if min_params:
            filters["min_params"] = _normalize_param_size(min_params)
        if max_params:
            filters["max_params"] = _normalize_param_size(max_params)
        
        # S'assurer que la plage est cohérente (min <= max)
        if filters.get("min_params") and filters.get("max_params"):
            try:
                min_v = float(filters["min_params"][:-1])  # retire le suffixe 'B'
                max_v = float(filters["max_params"][:-1])
                if min_v > max_v:
                    filters["min_params"], filters["max_params"] = filters["max_params"], filters["min_params"]
            except Exception:
                # En cas de format inattendu, on laisse tel quel
                pass
    elif parameter_size:
        # Only use exact parameter_size if range is not specified
        filters["parameter_size"] = parameter_size

    try:
        models = hf_client().search_gguf_models(
            query=query,
            limit=limit,
            sort=sort,
            filter_params=filters
        )
    except Exception as e:
        if request.headers.get("HX-Request"):
            return Response(
                f"<div class='col-span-full p-4 bg-red-50 dark:bg-red-900/20 text-red-600 rounded-xl text-sm'>Erreur de recherche: {escape(str(e))}</div>",
                mimetype="text/html"
            )
        return jsonify({"error": str(e)}), 500

    # Return JSON if requested
    if request.headers.get("Accept") == "application/json" and not request.headers.get("HX-Request"):
        return jsonify({"models": models})

    # Return HTML for HTMX
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

        # Format downloads
        if downloads >= 1000000:
            downloads_str = f"{downloads/1000000:.1f}M"
        elif downloads >= 1000:
            downloads_str = f"{downloads/1000:.1f}K"
        else:
            downloads_str = str(downloads)

        # Create card
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

        # List GGUF files
        for file in gguf_files[:15]:  # Limit to 15 files
            filename = escape(file.get("filename", ""))
            size = file.get("size", 0)
            quantization_level = escape(file.get("quantization", "") or "")
            param_size = escape(file.get("parameter_size", "") or "")

            # Format size
            if size >= 1024 * 1024 * 1024:
                size_str = f"{size / (1024**3):.2f} GB"
            else:
                size_str = f"{size / (1024**2):.1f} MB"

            safe_file_id = re.sub(r"[^a-zA-Z0-9_-]", "-", f"{model_id}-{filename}")

            # Badge Colors for Quantization
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


@api_huggingface_bp.post("/huggingface/pull")
def pull_gguf() -> Response:
    """
    Start downloading a GGUF model from HuggingFace
    """
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

    # Return HTML widget with progress bar for HTMX
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
    """
    Get detailed information about a specific HuggingFace model
    """
    try:
        model = hf_client().get_model_info(model_id)
        return jsonify(model)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_huggingface_bp.get("/huggingface/quantizations")
def get_quantizations() -> Response:
    """
    Get list of available quantization levels
    """
    return jsonify({"quantizations": hf_client().get_available_quantizations()})


@api_huggingface_bp.get("/huggingface/parameter_sizes")
def get_parameter_sizes() -> Response:
    """
    Get list of common parameter sizes
    """
    return jsonify({"parameter_sizes": hf_client().get_available_parameter_sizes()})


def _normalize_param_size(value: str) -> str:
    """
    Normalise une valeur saisie pour le filtre de nombre de paramètres.
    Accepte "7", "7B", "1.7", "1.7B", "0" et renvoie toujours en "xB".
    Ne modifie pas les valeurs déjà en "B" (insensible à la casse).
    """
    v = (value or "").strip()
    if not v:
        return ""
    v = v.upper()
    # Déjà au bon format X(.Y)B
    if re.fullmatch(r"\d+(\.\d+)?B", v):
        return v
    # Valeur numérique sans suffixe
    if re.fullmatch(r"\d+(\.\d+)?", v):
        return v + "B"
    # Sinon, renvoyer tel quel (ex: valeurs avancées non prévues)
    return v
