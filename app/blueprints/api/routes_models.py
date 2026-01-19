from __future__ import annotations

import re
import json
from flask import Blueprint, jsonify, request, current_app, Response
from markupsafe import escape
from ...extensions import cache
from ...services.ollama_client import OllamaClient
from ...services.tasks import enqueue_pull_model, enqueue_check_update, enqueue_eject_force
from ...utils import get_effective_ollama_base_url
from ...services.remote_search import model_details
from ...services.ollama_web import OllamaWebClient
from ...services.progress_bus import ProgressBus
from ...services.model_metadata_service import get_model_metadata, delete_model_metadata, refresh_model_metadata


api_models_bp = Blueprint("api_models", __name__)


def client() -> OllamaClient:
    return OllamaClient(
        base_url=get_effective_ollama_base_url(),
        connect_timeout=current_app.config["HTTP_CONNECT_TIMEOUT"],
        read_timeout=current_app.config["HTTP_READ_TIMEOUT"],
    )


def models_cache_key():
    """Generate a cache key that includes the effective Ollama base URL."""
    base_url = get_effective_ollama_base_url()
    # Include query string to respect search/filter
    qs = request.query_string.decode("utf-8")
    return f"models_list:{base_url}:{qs}"


def detect_model_capabilities(name: str, details: dict) -> list:
    """
    Detect model capabilities based on name patterns and details.
    Returns a list of capability strings: 'embedding', 'vision', 'tools', 'code', 'thinking'
    """
    capabilities = []
    name_lower = name.lower()
    families = details.get("families", []) if isinstance(details, dict) else []
    
    # Embedding models
    embedding_patterns = ['embed', 'bge-', 'bge:', 'all-minilm', 'snowflake-arctic', 'paraphrase', '/e5-', ':e5-', '/e5:', 'gte-', 'gte:', 'jina-']
    if any(p in name_lower for p in embedding_patterns):
        capabilities.append('embedding')
    
    # Vision models - check families first for multimodal models
    families_lower = [f.lower() for f in families] if isinstance(families, list) else []
    vision_patterns = [
        'vision', 'llava', 'bakllava', 'moondream', 'minicpm-v', 'minicpm:v',
        'phi3-vision', 'phi-3-vision', 'phi3.5-vision',
        'granite-vision', 'llama-vision', 'llama3.2-vision',
        'gemma2-vision', 'pixtral', 'internvl', 'cogvlm', 'yi-vl',
        'qwen-vl', 'qwen2-vl', 'qwenvl', 'glm-4v', 'internlm-xcomposer',
        'deepseek-vl', 'monkey', 'idefics', 'fuyu', 'kosmos'
    ]
    if any(p in name_lower for p in vision_patterns) or 'clip' in families_lower:
        capabilities.append('vision')
    
    # Code models
    code_patterns = ['code', 'codellama', 'deepseek-coder', 'starcoder', 'codegemma', 'codestral', 'qwen2.5-coder']
    if any(p in name_lower for p in code_patterns):
        capabilities.append('code')
    
    # Tools/Function calling models
    tools_patterns = ['tools', '-fc', 'functionary', 'hermes-3', 'firefunction', 'nexusraven']
    if any(p in name_lower for p in tools_patterns):
        capabilities.append('tools')
    
    # Thinking/Reasoning models
    thinking_patterns = ['deepseek-r1', 'qwq', 'o1-', 'reflection']
    if any(p in name_lower for p in thinking_patterns):
        capabilities.append('thinking')
    
    return capabilities


@api_models_bp.get("/models")
@cache.cached(timeout=10, key_prefix=models_cache_key)
def list_models() -> Response:
    q = (request.args.get("q") or "").strip().lower()
    view = request.args.get("view")
    
    items = []
    error = None
    provider_type = "ollama"  # Default
    provider_name = "Ollama"
    
    # Check if there's an active non-Ollama provider
    try:
        from ...services.provider_manager import get_provider_manager
        mgr = get_provider_manager()
        active_provider = mgr.get_active_provider()
        
        if active_provider and active_provider.get("type") == "lmstudio":
            provider_type = "lmstudio"
            provider_name = active_provider.get("name", "LM Studio")
            
            # Get models from LM Studio
            from ...services.llm_clients.openai_compatible_client import OpenAICompatibleClient
            full_provider = mgr.get_provider(active_provider["id"], include_api_key=True)
            if full_provider and full_provider.get("url"):
                lm_client = OpenAICompatibleClient(
                    provider_type="lmstudio",
                    base_url=full_provider.get("url"),
                    api_key=full_provider.get("api_key", "")
                )
                lm_models = lm_client.list_models()
                # Transform to same format as Ollama
                for m in lm_models:
                    # Construire le context info
                    ctx = m.get("max_context_length", 0)
                    ctx_str = f"{ctx//1024}k" if ctx else "-"
                    
                    items.append({
                        "name": m.get("id", m.get("name", "?")),
                        "size": 0,  # LM Studio API doesn't provide size
                        "details": {
                            "family": m.get("arch", "-"),
                            "quantization_level": m.get("quantization", "-"),
                            "parameter_size": ctx_str
                        },
                        "state": m.get("state", "not-loaded"),
                        "type": m.get("type", "llm"),
                        "publisher": m.get("publisher", ""),
                        "provider": "lmstudio"
                    })
        else:
            # Fallback to Ollama
            data = client().tags()
            items = data.get("models", []) if isinstance(data, dict) else data
            for m in items:
                m["provider"] = "ollama"
    except Exception as e:
        # Try Ollama as fallback
        try:
            data = client().tags()
            items = data.get("models", []) if isinstance(data, dict) else data
            for m in items:
                m["provider"] = "ollama"
        except Exception as e2:
            if request.headers.get("Accept") == "application/json":
                return jsonify({"error": str(e2)}), 500
            error = str(e2)
    
    if q:
        items = [m for m in items if q in (m.get("name", "").lower())]

    # JSON Return
    if request.headers.get("Accept") == "application/json" and not request.headers.get("HX-Request"):
         return jsonify({"models": items})
    
    # List Layout (Table Rows)
    if view == "list":
        html = []
        if error:
            # Message convivial pour guider l'utilisateur
            error_html = """
            <div class='col-span-12 text-center py-12'>
                <div class='mx-auto w-16 h-16 bg-amber-100 dark:bg-amber-900/30 rounded-2xl flex items-center justify-center mb-4'>
                    <svg class='w-8 h-8 text-amber-600 dark:text-amber-400' fill='none' viewBox='0 0 24 24' stroke='currentColor'>
                        <path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' />
                    </svg>
                </div>
                <h3 class='text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-2'>Ollama indisponible</h3>
                <p class='text-sm text-zinc-500 dark:text-zinc-400 mb-4 max-w-md mx-auto'>
                    Impossible de se connecter à Ollama. Vérifiez qu'il est démarré ou configurez-le dans les paramètres.
                </p>
                <a href='/settings#providers' class='inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-medium transition-colors'>
                    <svg class='w-4 h-4' fill='none' viewBox='0 0 24 24' stroke='currentColor'>
                        <path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' />
                        <path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M15 12a3 3 0 11-6 0 3 3 0 016 0z' />
                    </svg>
                    Configurer Ollama
                </a>
            </div>
            """
            return Response(error_html, mimetype="text/html")
        if not items:
            return Response("<div class='col-span-12 text-center py-8 text-zinc-500'>No models installed.</div>", mimetype="text/html")
            
        for m in items:
            name = escape(m.get("name", "?"))
            size = m.get("size", 0)
            size_fmt = f"{size/1024/1024/1024:.2f} GB" if size else "-"
            details = m.get("details", {})
            family = escape(details.get("family", "-"))
            quant = escape(details.get("quantization_level", "-"))
            param_size = escape(details.get("parameter_size", "-"))
            provider = m.get("provider", "ollama")
            model_state = m.get("state", "")
            
            # Provider badge
            if provider == "lmstudio":
                provider_badge = '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400">LM Studio</span>'
                # State badge for LM Studio models
                if model_state == "loaded":
                    state_badge = '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">● Loaded</span>'
                else:
                    state_badge = ''
            else:
                provider_badge = ''
                state_badge = ''
            
            # Get capabilities from cache or API
            model_name_raw = m.get("name", "")
            metadata = get_model_metadata(model_name_raw)
            if metadata:
                capabilities = metadata.get("capabilities", [])
                # Update param_size from metadata if available
                if metadata.get("parameter_size"):
                    param_size = escape(metadata.get("parameter_size"))
            else:
                # Fallback to pattern-based detection
                capabilities = detect_model_capabilities(model_name_raw, details)
            
            # Generate capability badges
            badge_colors = {
                'embedding': 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
                'vision': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
                'code': 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
                'tools': 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
                'thinking': 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300'
            }
            badges_html = ""
            for cap in capabilities:
                color = badge_colors.get(cap, 'bg-zinc-100 text-zinc-600')
                badges_html += f'<span class="px-1.5 py-0.5 rounded text-xs font-medium {color}">{cap}</span>'
            
            # Add provider and state badges
            badges_html = f'{provider_badge} {state_badge} {badges_html}'
            
            # Actions - pour LM Studio, seulement Chat est disponible
            if provider == "lmstudio":
                actions_html = f"""
                      <a href="/chat?model={name}" class="p-2 rounded-lg text-zinc-400 hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors" title="Chat">
                         <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                      </a>
                """
            else:
                actions_html = f"""
                      <a href="/chat?model={name}" class="p-2 rounded-lg text-zinc-400 hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors" title="Chat">
                         <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                      </a>
                      <a href="/models/{name}" class="p-2 rounded-lg text-zinc-400 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors hidden sm:block" title="Voir">
                         <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                      </a>
                      <a href="/models/{name}/edit" class="p-2 rounded-lg text-zinc-400 hover:text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-colors hidden sm:block" title="Modifier">
                         <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                      </a>
                      <button class="p-2 rounded-lg text-zinc-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors" title="Update"
                              hx-post="/api/models/pull" hx-vals='{{"name": "{name}"}}' hx-target="#toast-container" hx-swap="beforeend">
                          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                      </button>
                      <button class="p-2 rounded-lg text-zinc-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors hidden sm:block" title="Delete"
                              onclick="(function(btn){{showConfirmDialog({{title: 'Supprimer le modèle', message: 'Voulez-vous vraiment supprimer <strong>{name}</strong> ? Cette action est irréversible.', type: 'danger', confirmText: 'Supprimer', onConfirm: () => fetch('/api/models/{name}', {{method: 'DELETE'}}).then(() => btn.closest('.group').remove())}})}})(this)">
                          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                      </button>
                """
            
            html.append(f"""
            <div class="grid grid-cols-4 md:grid-cols-12 px-6 py-4 items-center hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors group">
                 <div class="col-span-2 md:col-span-3 flex items-center gap-4">
                     <div class="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 flex items-center justify-center font-bold text-xs shrink-0">
                        {name[:2].upper()}
                     </div>
                     <div>
                        <div class="font-medium text-zinc-900 dark:text-zinc-100 truncate">{name}</div>
                        <div class="flex items-center gap-1 mt-0.5 flex-wrap">{badges_html}</div>
                     </div>
                 </div>
                 <div class="hidden md:block md:col-span-1 text-sm text-zinc-500 dark:text-zinc-400">
                    <span class="px-2 py-1 bg-zinc-100 dark:bg-zinc-800 rounded text-xs font-mono font-semibold">{param_size}</span>
                 </div>
                 <div class="hidden md:block md:col-span-2 text-sm text-zinc-500 dark:text-zinc-400">
                    <span class="px-2 py-1 bg-zinc-100 dark:bg-zinc-800 rounded text-xs font-mono">{family}</span>
                 </div>
                 <div class="col-span-1 md:col-span-2 text-sm text-zinc-500 dark:text-zinc-400">{size_fmt}</div>
                 <div class="hidden md:block md:col-span-2 text-sm text-zinc-500 dark:text-zinc-400 font-mono">{quant}</div>
                 <div class="col-span-1 md:col-span-2 flex justify-end gap-2 opacity-100 md:opacity-0 group-hover:opacity-100 transition-opacity">
                     {actions_html}
                 </div>
            </div>
            """)
        return Response("".join(html), mimetype="text/html")

    # Grid Layout (Default)
    html = ["<div id=\"models\" class=\"grid gap-4 sm:grid-cols-2 xl:grid-cols-3\">"]
    if error:
        # Message convivial pour guider l'utilisateur
        error_block = """
        <div class="sm:col-span-2 xl:col-span-3">
            <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-2xl p-6 text-center">
                <div class="mx-auto w-12 h-12 bg-amber-100 dark:bg-amber-900/30 rounded-xl flex items-center justify-center mb-3">
                    <svg class="w-6 h-6 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                </div>
                <h3 class="font-semibold text-amber-800 dark:text-amber-200 mb-1">Ollama indisponible</h3>
                <p class="text-sm text-amber-700 dark:text-amber-300 mb-3">Vérifiez qu'Ollama est démarré ou configurez-le.</p>
                <a href="/settings#providers" class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium transition-colors">
                    Configurer Ollama
                </a>
            </div>
        </div>
        """
        html.append(error_block)
    if not items:
        html.append("<div class=\"sm:col-span-2 xl:col-span-3\"><p class=\"text-sm text-slate-500 dark:text-zinc-400\">Aucun modèle.</p></div>")
    for m in items:
        raw_name = m.get("name", "?")
        name = escape(raw_name)
        safe_id = "pull-" + re.sub(r"[^a-zA-Z0-9_-]", "-", str(raw_name))
        size = m.get("size", 0)
        size_mb = f"{size/1024/1024:.1f} Mo" if isinstance(size, (int, float)) else ""
        # Format date
        modified_at = m.get("modified_at", "")
        date_str = ""
        if modified_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(modified_at.replace("Z", "+00:00"))
                date_str = dt.strftime("%d/%m/%Y")
            except Exception:
                date_str = ""
        html.append(
            """
            <div class=\"group bg-white dark:bg-zinc-800 rounded-xl shadow-card p-4 flex flex-col gap-3 border border-zinc-200 dark:border-zinc-700\">
              <div class=\"flex items-start justify-between\">
                <div>
                  <a class=\"font-semibold text-zinc-900 dark:text-zinc-100 hover:text-brand-700 dark:hover:text-brand-400\" href=\"/models/{name}\">{name}</a>
                  <div class=\"text-xs text-zinc-500 dark:text-zinc-400\">{size_mb}</div>
                  <div class=\"text-xs text-zinc-500 dark:text-zinc-400\">{date_str}</div>
                </div>
              </div>
              <div class=\"flex items-center gap-2\">
                <form hx-post=\"/api/models/pull\" hx-target=\"#{safe_id}\" class=\"inline\">
                  <input type=\"hidden\" name=\"name\" value=\"{name}\"/>
                  <button class=\"text-sm rounded-lg bg-brand-600 hover:bg-brand-500 text-white px-3 py-1.5\">Mettre à jour</button>
                </form>
                <a href=\"/models/{name}/edit\" class=\"text-sm rounded-lg border border-purple-300 dark:border-purple-600 text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/20 px-3 py-1.5\">Modifier</a>
                <a href=\"/models/{name}\" class=\"text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-50 dark:hover:bg-zinc-700 px-3 py-1.5\">Détails</a>
              </div>
              <div id=\"{safe_id}\" class=\"text-xs text-zinc-500 dark:text-zinc-400\"></div>
            </div>
            """.replace("{name}", str(name)).replace("{size_mb}", str(size_mb)).replace("{safe_id}", str(safe_id)).replace("{date_str}", str(date_str))
        )
    html.append("</div>")
    return Response("".join(html), mimetype="text/html")


@api_models_bp.post("/models/show")
def show_model() -> Response:
    # Support both JSON and form data (HTMX sends form data)
    if request.is_json:
        name = (request.json or {}).get("name")
    else:
        name = request.values.get("name") or request.form.get("name")
    
    if not name:
        if request.headers.get("HX-Request"):
            return Response(
                "<div id='details' class='text-sm text-red-600 dark:text-red-400'>Paramètre name manquant</div>",
                mimetype="text/html"
            ), 400
        return jsonify({"error": "name requis"}), 400
    # Try to fetch details; if it fails (e.g., reverse proxy missing /api/show), handle gracefully
    err: str | None = None
    data = {}
    try:
        data = client().show(name)
    except Exception as e:
        err = str(e)
    # If HTML requested (HTMX), render a card-like summary
    accept = request.headers.get("Accept", "")
    if "text/html" in accept or request.headers.get("HX-Request"):
        details = []
        if isinstance(data, dict) and not err:
            # Extract all useful information from the response
            modelfile = data.get("modelfile", "")
            parameters = data.get("parameters", "")
            template = data.get("template", "")
            details_data = data.get("details", {})
            license_text = data.get("license", "")
            
            # Model details
            digest = data.get("digest")
            size = details_data.get("size") if isinstance(details_data, dict) else data.get("size")
            format_type = details_data.get("format") if isinstance(details_data, dict) else None
            family = details_data.get("family") if isinstance(details_data, dict) else None
            families = details_data.get("families") if isinstance(details_data, dict) else None
            parameter_size = details_data.get("parameter_size") if isinstance(details_data, dict) else None
            quantization = details_data.get("quantization_level") if isinstance(details_data, dict) else None
            parent = data.get("parent_model")
            
            # Format size
            size_mb = f"{(size or 0)/1024/1024:.1f} Mo" if isinstance(size, (int, float)) else ""
            size_gb = f"{(size or 0)/1024/1024/1024:.2f} Go" if isinstance(size, (int, float)) and size > 1024*1024*1024 else ""
            
            # Build details sections
            details.append("<div class='space-y-3'>")
            
            # Basic info
            details.append("<div class='border-b border-zinc-200 dark:border-zinc-700 pb-2'>")
            details.append("<h3 class='font-medium text-sm mb-2'>Informations principales</h3>")
            if digest:
                details.append(f"<div class='text-sm text-zinc-600 dark:text-zinc-300'><span class='font-medium'>Digest:</span> <code class='text-xs bg-zinc-100 dark:bg-zinc-900 px-1 rounded'>{escape(str(digest)[:16])}...</code></div>")
            if size:
                display_size = size_gb if size_gb else size_mb
                details.append(f"<div class='text-sm text-zinc-600 dark:text-zinc-300'><span class='font-medium'>Taille:</span> {escape(display_size)}</div>")
            if format_type:
                details.append(f"<div class='text-sm text-zinc-600 dark:text-zinc-300'><span class='font-medium'>Format:</span> {escape(str(format_type))}</div>")
            if family:
                details.append(f"<div class='text-sm text-zinc-600 dark:text-zinc-300'><span class='font-medium'>Famille:</span> {escape(str(family))}</div>")
            if families and isinstance(families, list):
                details.append(f"<div class='text-sm text-zinc-600 dark:text-zinc-300'><span class='font-medium'>Familles:</span> {escape(', '.join(str(f) for f in families))}</div>")
            if parameter_size:
                details.append(f"<div class='text-sm text-zinc-600 dark:text-zinc-300'><span class='font-medium'>Paramètres:</span> {escape(str(parameter_size))}</div>")
            if quantization:
                details.append(f"<div class='text-sm text-zinc-600 dark:text-zinc-300'><span class='font-medium'>Quantification:</span> {escape(str(quantization))}</div>")
            if parent:
                details.append(f"<div class='text-sm text-zinc-600 dark:text-zinc-300'><span class='font-medium'>Parent:</span> {escape(str(parent))}</div>")
            details.append("</div>")
            
            # Parameters
            if parameters:
                details.append("<div class='border-b border-zinc-200 dark:border-zinc-700 pb-2'>")
                details.append("<h3 class='font-medium text-sm mb-2'>Paramètres</h3>")
                details.append(f"<pre class='text-xs bg-zinc-100 dark:bg-zinc-900 p-2 rounded overflow-x-auto'>{escape(str(parameters))}</pre>")
                details.append("</div>")
            
            # Template
            if template:
                template_preview = str(template)[:200] + ("..." if len(str(template)) > 200 else "")
                details.append("<div class='border-b border-zinc-200 dark:border-zinc-700 pb-2'>")
                details.append("<h3 class='font-medium text-sm mb-2'>Template</h3>")
                details.append(f"<pre class='text-xs bg-zinc-100 dark:bg-zinc-900 p-2 rounded overflow-x-auto'>{escape(template_preview)}</pre>")
                details.append("</div>")
            
            # License
            if license_text:
                license_preview = str(license_text)[:300] + ("..." if len(str(license_text)) > 300 else "")
                details.append("<div>")
                details.append("<h3 class='font-medium text-sm mb-2'>Licence</h3>")
                details.append(f"<pre class='text-xs bg-zinc-100 dark:bg-zinc-900 p-2 rounded overflow-x-auto whitespace-pre-wrap'>{escape(license_preview)}</pre>")
                details.append("</div>")
            
            details.append("</div>")
        # Fallback to remote details when local show fails
        remote = None
        if err:
            base_model = str(name).split(":")[0]
            remote = model_details(base_model)
            desc = remote.get("description") or "Détails indisponibles"
            link = remote.get("link")
            variants = remote.get("variants") or []
            details.append(f"<div class='text-sm text-zinc-600 dark:text-zinc-300'>{escape(desc)}</div>")
            if link:
                details.append(f"<div class='mt-2 text-xs'><a class='text-brand-600 dark:text-brand-400 underline' href='{escape(link)}' target='_blank' rel='noopener'>Voir sur ollama.com</a></div>")
            if variants:
                # Offer quick actions for variants
                chips = []
                for t in variants[:12]:
                    full = f"{base_model}:{t}"
                    chips.append(
                        f"<form hx-post='/api/models/pull' hx-target='#details' class='inline-block mr-2 mt-2'>"
                        f"<input type='hidden' name='name' value='{escape(full)}'/>"
                        f"<button class='text-xs rounded-full bg-brand-600 hover:bg-brand-500 text-white px-3 py-1'>Pull {escape(t)}</button>"
                        f"</form>"
                    )
                details.append("<div class='mt-2'>" + "".join(chips) + "</div>")
        error_html = (
            f"<div class='text-sm text-red-600 dark:text-red-400'>Détails indisponibles depuis l'endpoint: {escape(err) if err else ''}</div>"
            if err else ""
        )
        html = (
            "<div id='details' class='bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-xl shadow-card p-4'>"
            f"<div class='text-zinc-900 dark:text-zinc-100 font-semibold mb-2'>{escape(name)}</div>"
            + (error_html or ("".join(details) or "<div class='text-sm text-zinc-500 dark:text-zinc-400'>Aucun détail.</div>"))
            + "</div>"
        )
        return Response(html, mimetype="text/html")
    if err:
        return jsonify({"error": err}), 502
    return jsonify(data)


@api_models_bp.get("/models/<name>/details")
def model_details_html(name: str) -> Response:
    """Generate beautiful HTML for model details page."""
    err: str | None = None
    data = {}
    try:
        data = client().show(name)
    except Exception as e:
        err = str(e)
    
    if err:
        return Response(
            f"""<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 text-center">
                <svg class="w-12 h-12 mx-auto text-red-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <h3 class="text-lg font-semibold text-red-700 dark:text-red-300 mb-2">Erreur de chargement</h3>
                <p class="text-red-600 dark:text-red-400">{escape(err)}</p>
            </div>""",
            mimetype="text/html"
        )
    
    # Extract data
    details_data = data.get("details", {}) if isinstance(data, dict) else {}
    
    # Get size and digest from show response, but if not available, fetch from tags API
    size = data.get("size") or details_data.get("size") or 0
    digest_raw = data.get("digest", "")
    
    if not size or not digest_raw:
        try:
            tags_data = client().tags()
            models_list = tags_data.get("models", []) if isinstance(tags_data, dict) else []
            for m in models_list:
                if m.get("name") == name:
                    if not size:
                        size = m.get("size", 0)
                    if not digest_raw:
                        digest_raw = m.get("digest", "")
                    break
        except Exception:
            pass
    
    digest = digest_raw[:16] + "..." if digest_raw else "-"
    size_gb = f"{size/1024/1024/1024:.2f} GB" if size else "-"
    format_type = details_data.get("format", "-")
    family = details_data.get("family", "-")
    families = details_data.get("families", [])
    parameter_size = details_data.get("parameter_size", "-")
    quantization = details_data.get("quantization_level", "-")
    parent = data.get("parent_model", "")
    template = data.get("template", "")
    parameters = data.get("parameters", "")
    license_text = data.get("license", "")
    system_prompt = data.get("system", "")
    
    # Build architecture badges
    arch_badges = ""
    if families:
        for f in families:
            arch_badges += f'<span class="text-xs bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-300 px-2 py-1 rounded-lg">{escape(f)}</span> '
    else:
        arch_badges = '<span class="text-zinc-400">-</span>'
    
    # Build parent row
    parent_row = ""
    if parent:
        parent_row = f"""
                <div class="px-6 py-4 flex justify-between items-center">
                    <span class="text-zinc-500 dark:text-zinc-400">Modèle parent</span>
                    <span class="font-mono text-sm bg-zinc-100 dark:bg-zinc-800 px-3 py-1 rounded-lg">{escape(parent)}</span>
                </div>"""
    
    # Build system prompt section
    system_section = ""
    if system_prompt:
        system_section = f"""
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
            <div class="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
                <h3 class="font-semibold text-zinc-900 dark:text-zinc-100">System Prompt</h3>
            </div>
            <div class="p-6">
                <pre class="text-sm bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl overflow-x-auto whitespace-pre-wrap text-zinc-700 dark:text-zinc-300 max-h-64 overflow-y-auto">{escape(system_prompt)}</pre>
            </div>
        </div>"""
    
    # Build parameters section
    params_section = ""
    if parameters:
        params_section = f"""
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
            <div class="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
                <h3 class="font-semibold text-zinc-900 dark:text-zinc-100">Paramètres du modèle</h3>
            </div>
            <div class="p-6">
                <pre class="text-sm bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl overflow-x-auto font-mono text-zinc-700 dark:text-zinc-300">{escape(parameters)}</pre>
            </div>
        </div>"""
    
    # Template content
    template_content = escape(template) if template else "Aucun template défini"
    license_content = escape(license_text) if license_text else "Aucune licence disponible"
    
    # Build final HTML
    html = f"""
    <!-- Stats Cards -->
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-5">
            <div class="flex items-center gap-3 mb-3">
                <div class="p-2.5 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                    <svg class="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                    </svg>
                </div>
                <span class="text-sm text-zinc-500 dark:text-zinc-400">Paramètres</span>
            </div>
            <div class="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{escape(str(parameter_size))}</div>
        </div>
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-5">
            <div class="flex items-center gap-3 mb-3">
                <div class="p-2.5 bg-purple-50 dark:bg-purple-900/20 rounded-xl">
                    <svg class="w-5 h-5 text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                    </svg>
                </div>
                <span class="text-sm text-zinc-500 dark:text-zinc-400">Taille</span>
            </div>
            <div class="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{escape(size_gb)}</div>
        </div>
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-5">
            <div class="flex items-center gap-3 mb-3">
                <div class="p-2.5 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
                    <svg class="w-5 h-5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                </div>
                <span class="text-sm text-zinc-500 dark:text-zinc-400">Quantification</span>
            </div>
            <div class="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{escape(str(quantization))}</div>
        </div>
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-5">
            <div class="flex items-center gap-3 mb-3">
                <div class="p-2.5 bg-orange-50 dark:bg-orange-900/20 rounded-xl">
                    <svg class="w-5 h-5 text-orange-600 dark:text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
                    </svg>
                </div>
                <span class="text-sm text-zinc-500 dark:text-zinc-400">Famille</span>
            </div>
            <div class="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{escape(str(family))}</div>
        </div>
    </div>

    <!-- Info Tab Content -->
    <div x-show="activeTab === 'info'" class="space-y-6">
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
            <div class="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
                <h3 class="font-semibold text-zinc-900 dark:text-zinc-100">Informations techniques</h3>
            </div>
            <div class="divide-y divide-zinc-100 dark:divide-zinc-800">
                <div class="px-6 py-4 flex justify-between items-center">
                    <span class="text-zinc-500 dark:text-zinc-400">Format</span>
                    <span class="font-mono text-sm bg-zinc-100 dark:bg-zinc-800 px-3 py-1 rounded-lg">{escape(str(format_type))}</span>
                </div>
                <div class="px-6 py-4 flex justify-between items-center">
                    <span class="text-zinc-500 dark:text-zinc-400">Digest</span>
                    <span class="font-mono text-sm bg-zinc-100 dark:bg-zinc-800 px-3 py-1 rounded-lg">{escape(digest)}</span>
                </div>{parent_row}
                <div class="px-6 py-4 flex justify-between items-center">
                    <span class="text-zinc-500 dark:text-zinc-400">Architecture</span>
                    <div class="flex flex-wrap gap-2 justify-end">
                        {arch_badges}
                    </div>
                </div>
            </div>
        </div>
        {system_section}
        {params_section}
    </div>

    <!-- Template Tab Content -->
    <div x-show="activeTab === 'template'" style="display: none;" class="space-y-6">
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
            <div class="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
                <h3 class="font-semibold text-zinc-900 dark:text-zinc-100">Template de prompt</h3>
                <button onclick="navigator.clipboard.writeText(document.getElementById('template-content').textContent)" 
                        class="text-sm text-brand-600 hover:text-brand-500 flex items-center gap-1">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copier
                </button>
            </div>
            <div class="p-6">
                <pre id="template-content" class="text-sm bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl overflow-x-auto whitespace-pre-wrap font-mono text-zinc-700 dark:text-zinc-300 max-h-96 overflow-y-auto">{template_content}</pre>
            </div>
        </div>
    </div>

    <!-- License Tab Content -->
    <div x-show="activeTab === 'license'" style="display: none;" class="space-y-6">
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
            <div class="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
                <h3 class="font-semibold text-zinc-900 dark:text-zinc-100">Licence</h3>
            </div>
            <div class="p-6">
                <pre class="text-sm bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl overflow-x-auto whitespace-pre-wrap text-zinc-700 dark:text-zinc-300 max-h-96 overflow-y-auto">{license_content}</pre>
            </div>
        </div>
    </div>

    <!-- Actions Tab Content -->
    <div x-show="activeTab === 'actions'" style="display: none;" class="space-y-6">
        <div class="grid gap-4 sm:grid-cols-2">
            <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6">
                <div class="flex items-center gap-3 mb-4">
                    <div class="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                        <svg class="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                    </div>
                    <div>
                        <h4 class="font-semibold text-zinc-900 dark:text-zinc-100">Mettre à jour</h4>
                        <p class="text-sm text-zinc-500 dark:text-zinc-400">Re-télécharger la dernière version</p>
                    </div>
                </div>
                <form hx-post="/api/models/pull" hx-target="#action-out" hx-swap="innerHTML">
                    <input type="hidden" name="name" value="{escape(name)}"/>
                    <button type="submit" class="w-full px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium transition-all">
                        Lancer la mise à jour
                    </button>
                </form>
            </div>
            <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6">
                <div class="flex items-center gap-3 mb-4">
                    <div class="p-3 bg-green-50 dark:bg-green-900/20 rounded-xl">
                        <svg class="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" />
                        </svg>
                    </div>
                    <div>
                        <h4 class="font-semibold text-zinc-900 dark:text-zinc-100">Copier / Renommer</h4>
                        <p class="text-sm text-zinc-500 dark:text-zinc-400">Créer une copie avec un nouveau nom</p>
                    </div>
                </div>
                <form hx-post="/api/models/copy" hx-target="#action-out" hx-swap="innerHTML" class="flex gap-2">
                    <input type="hidden" name="source" value="{escape(name)}"/>
                    <input type="text" name="dest" placeholder="nouveau-nom:tag" 
                           class="flex-1 px-4 py-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:ring-2 focus:ring-brand-500/20"/>
                    <button type="submit" class="px-4 py-2.5 rounded-xl bg-green-600 hover:bg-green-500 text-white font-medium transition-all">
                        Copier
                    </button>
                </form>
            </div>
        </div>
    </div>
    """
    
    return Response(html, mimetype="text/html")


@api_models_bp.post("/models/pull")
def pull_model() -> Response:
    name = request.values.get("name") or (request.json or {}).get("name")
    if not name:
        return jsonify({"error": "name requis"}), 400
    job_id = enqueue_pull_model(name, base_url=get_effective_ollama_base_url())
    # Return small HTML widget that listens to SSE
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
            # Supprimer les métadonnées du cache
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
    
    # Check if Accept header wants SSE
    accept = request.headers.get("Accept", "")
    want_sse = "text/event-stream" in accept
    
    # Instantiate client here to capture application context (current_app)
    # before entering the generator which might run outside context
    ollama = client()

    def generate_sse():
        print(f"!!! DEBUG ROUTES: Starting create_model for {name} from {from_model} !!!", flush=True)
        try:
            for chunk in ollama.create_model(
                name=name,
                from_model=from_model,
                system=system,
                template=template,
                parameters=parameters
            ):
                if "error" in chunk:
                    print(f"!!! DEBUG ROUTES: Error chunk received: {chunk} !!!", flush=True)
                    yield f"data: {json.dumps({'error': chunk['error']})}\n\n"
                    return
                yield f"data: {json.dumps(chunk)}\n\n"
            
            print("!!! DEBUG ROUTES: Creation complete !!!", flush=True)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            print(f"!!! DEBUG ROUTES: Exception: {e} !!!", flush=True)
            yield f"data: {{\"status\": \"Erreur\", \"error\": \"{escape(str(e))}\", \"done\": true}}\n\n"
    
    if want_sse:
        return Response(
            generate_sse(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )
    
    # Non-streaming response
    try:
        result = None
        for evt in client().create_model(
            name=name,
            from_model=from_model,
            system=system,
            template=template,
            parameters=parameters
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
            msg = f"Copie {escape(source)} → {escape(dest)} réussie" if ok else f"Échec copie"
            color = "text-green-600 dark:text-green-400" if ok else "text-red-600 dark:text-red-400"
            return Response(
                f"<div id='action-out' class='text-sm {color}'>{msg}</div>",
                mimetype="text/html"
            )
        return jsonify({"copied": ok})
    except Exception as e:
        if request.headers.get("HX-Request"):
            return Response(
                f"<div id='action-out' class='text-sm text-red-600 dark:text-red-400'>Erreur: {escape(str(e))}</div>",
                mimetype="text/html"
            )
        return jsonify({"error": str(e)}), 500


@api_models_bp.get("/stats")
def stats() -> Response:
    try:
        # Get models and running processes from Ollama
        client_inst = client()
        models_data = client_inst.tags()
        models_list = models_data.get("models", []) if isinstance(models_data, dict) else []
        
        ps_data = client_inst.ps()
        running_list = ps_data.get("models", []) if isinstance(ps_data, dict) else []
        
        total_models = len(models_list)
        active_models = len(running_list)
        
        # Also count LM Studio loaded models
        lmstudio_active = 0
        try:
            from ...services.provider_manager import get_provider_manager
            from ...services.llm_clients.openai_compatible_client import OpenAICompatibleClient
            
            mgr = get_provider_manager()
            providers = mgr.get_providers()
            
            for provider in providers:
                if provider.get("type") == "lmstudio":
                    full_provider = mgr.get_provider(provider["id"], include_api_key=True)
                    if full_provider and full_provider.get("url"):
                        try:
                            lm_client = OpenAICompatibleClient(
                                provider_type="lmstudio",
                                base_url=full_provider.get("url"),
                                api_key=full_provider.get("api_key", "")
                            )
                            loaded = lm_client.list_loaded_models()
                            lmstudio_active += len(loaded)
                        except Exception:
                            pass
        except Exception:
            pass
        
        active_models += lmstudio_active
        
        # Calculate sizes
        total_size = sum(m.get("size", 0) for m in models_list)
        vram_usage = sum(m.get("size", 0) for m in running_list) # Approx
        
        # Format sizes
        def fmt_size(b):
            if b >= 1024**3: return f"{b/1024**3:.1f} GB"
            if b >= 1024**2: return f"{b/1024**2:.0f} MB"
            return f"{b} B"

        html = f"""
           <!-- Active Models -->
           <div class="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-card flex items-start flex-col justify-between">
              <div class="flex items-center justify-between w-full mb-4">
                 <div class="p-3 bg-brand-50 dark:bg-brand-900/20 rounded-xl text-brand-600">
                    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                 </div>
                 <span class="flex h-2 w-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></span>
              </div>
              <div>
                 <div class="text-3xl font-bold text-zinc-900 dark:text-zinc-100">{active_models} <span class="text-sm font-medium text-zinc-500 uppercase tracking-wider ml-1">Active</span></div>
                 <div class="text-sm text-zinc-500 dark:text-zinc-400 mt-1">Running Models</div>
              </div>
           </div>

           <!-- VRAM Usage -->
           <div class="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-card flex items-start flex-col justify-between">
              <div class="flex items-center justify-between w-full mb-4">
                 <div class="p-3 bg-purple-50 dark:bg-purple-900/20 rounded-xl text-purple-600">
                    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>
                 </div>
              </div>
              <div>
                 <div class="text-3xl font-bold text-zinc-900 dark:text-zinc-100">{fmt_size(vram_usage)}</div>
                 <div class="text-sm text-zinc-500 dark:text-zinc-400 mt-1">VRAM Usage (Approx)</div>
              </div>
           </div>

           <!-- Total Installed -->
           <div class="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-card flex items-start flex-col justify-between">
              <div class="flex items-center justify-between w-full mb-4">
                 <div class="p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl text-emerald-600">
                    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg>
                 </div>
              </div>
              <div>
                 <div class="text-3xl font-bold text-zinc-900 dark:text-zinc-100">{total_models} <span class="text-sm font-medium text-zinc-500 uppercase tracking-wider ml-1">Models</span></div>
                 <div class="text-sm text-zinc-500 dark:text-zinc-400 mt-1">Total Installed</div>
              </div>
           </div>

           <!-- Disk Usage -->
           <div class="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-card flex items-start flex-col justify-between">
              <div class="flex items-center justify-between w-full mb-4">
                 <div class="p-3 bg-orange-50 dark:bg-orange-900/20 rounded-xl text-orange-600">
                    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>
                 </div>
              </div>
              <div>
                 <div class="text-3xl font-bold text-zinc-900 dark:text-zinc-100">{fmt_size(total_size)}</div>
                 <div class="text-sm text-zinc-500 dark:text-zinc-400 mt-1">Disk Usage</div>
              </div>
           </div>
        """
        return Response(html, mimetype="text/html")
    except Exception as e:
        # Message convivial pour le dashboard
        error_html = """
        <div class="col-span-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-2xl p-6 text-center">
            <div class="mx-auto w-12 h-12 bg-amber-100 dark:bg-amber-900/30 rounded-xl flex items-center justify-center mb-3">
                <svg class="w-6 h-6 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            </div>
            <h3 class=\"font-semibold text-amber-800 dark:text-amber-200 mb-1\">Ollama indisponible</h3>
            <p class=\"text-sm text-amber-700 dark:text-amber-300 mb-3\">Impossible de se connecter à Ollama.</p>
            <a href=\"/settings#providers\" class=\"inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-colors\">
                Configurer Ollama
            </a>
        </div>
        """
        return Response(error_html, mimetype="text/html")


@api_models_bp.get("/stats/count")
def stats_count() -> Response:
    try:
        data = client().tags()
        items = data.get("models", []) if isinstance(data, dict) else []
        count = len(items)
        return Response(str(count), mimetype="text/plain")
    except Exception:
        return Response("0", mimetype="text/plain")


@api_models_bp.get("/models/recent")
def recent_models() -> Response:
    try:
        from datetime import datetime
        client_inst = client()
        models_data = client_inst.tags()
        items = models_data.get("models", []) if isinstance(models_data, dict) else []
        
        # Sort by modified_at desc
        items.sort(key=lambda x: x.get("modified_at", ""), reverse=True)
        recent = items[:3] # Top 3
        
        if not recent:
             return Response("<div class='text-zinc-500 text-sm'>No models installed.</div>", mimetype="text/html")
        
        html = []
        for m in recent:
             name = escape(m.get("name", "?"))
             modified = m.get("modified_at", "")
             # Parse date roughly
             date_str = "Unknown"
             if modified:
                 try:
                     dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                     # Simple relative time or format
                     delta = datetime.now(dt.tzinfo) - dt
                     if delta.days > 0:
                         date_str = f"{delta.days} days ago"
                     else:
                         hours = delta.seconds // 3600
                         if hours > 0: date_str = f"{hours} hours ago"
                         else: date_str = f"{delta.seconds // 60} minutes ago"
                 except: pass

             # Determine icon/family
             family = (m.get("details", {}).get("family") or "llama").lower()
             # Simple icon mapping based on name/family could be here
             
             html.append(f"""
             <div class="bg-white dark:bg-zinc-900 rounded-2xl p-4 border border-zinc-200 dark:border-zinc-800 shadow-card flex items-center gap-4">
               <div class="w-12 h-12 rounded-xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-zinc-400">
                  <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
               </div>
               <div>
                  <div class="font-semibold text-zinc-900 dark:text-zinc-100">{name}</div>
                  <div class="text-xs text-zinc-500 dark:text-zinc-400">{date_str}</div>
               </div>
             </div>
             """)
        return Response("".join(html), mimetype="text/html")
    except Exception as e:
        # Message convivial pour recent_models
        error_html = """
        <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 text-center">
            <p class="text-sm font-medium text-amber-800 dark:text-amber-200">Ollama indisponible</p>
            <p class="text-xs text-amber-700 dark:text-amber-300 mt-1">Vérifiez qu'Ollama est démarré</p>
        </div>
        """
        return Response(error_html, mimetype="text/html")


@api_models_bp.get("/running")
def running() -> Response:
    error = None
    procs = []
    lmstudio_procs = []
    
    # 1. Get Ollama running models
    try:
        data = client().ps()
        procs = data.get("models", []) if isinstance(data, dict) else []
        # Add provider info to each model
        for p in procs:
            p["provider"] = "ollama"
    except Exception as e:
        error = str(e)
    
    # 2. Get LM Studio loaded models (if configured)
    try:
        from ...services.provider_manager import get_provider_manager
        from ...services.llm_clients.openai_compatible_client import OpenAICompatibleClient
        
        mgr = get_provider_manager()
        providers = mgr.get_providers()
        
        for provider in providers:
            if provider.get("type") == "lmstudio":
                # Get the full provider with URL
                full_provider = mgr.get_provider(provider["id"], include_api_key=True)
                if full_provider and full_provider.get("url"):
                    try:
                        lm_client = OpenAICompatibleClient(
                            provider_type="lmstudio",
                            base_url=full_provider.get("url"),
                            api_key=full_provider.get("api_key", "")
                        )
                        loaded = lm_client.list_loaded_models()
                        for m in loaded:
                            m["provider"] = "lmstudio"
                            m["provider_name"] = provider.get("name", "LM Studio")
                        lmstudio_procs.extend(loaded)
                    except Exception as lm_err:
                        current_app.logger.warning(f"Failed to get LM Studio models: {lm_err}")
    except Exception as e:
        current_app.logger.warning(f"Failed to check LM Studio providers: {e}")
    
    # Combine all running models
    all_procs = procs + lmstudio_procs
    
    # Important: conserver hx-trigger pour l'auto-actualisation après swap
    html = ["<div id=\"running\" hx-get=\"/api/running\" hx-trigger=\"every 5s\" hx-target=\"#running\" hx-swap=\"outerHTML\" class=\"space-y-3\">"]
    
    # Update running count badge if possible (via OOB swap)
    count = len(all_procs)
    html.append(f"<span id='running-count' hx-swap-oob='true' class='text-brand-600 font-bold'>{count}</span>")
    
    if error and not lmstudio_procs:
        # Message convivial au lieu de l'erreur technique
        error_block = """
        <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 flex items-start gap-3">
            <svg class="w-5 h-5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
                <p class="text-sm font-medium text-amber-800 dark:text-amber-200">Ollama indisponible</p>
                <p class="text-xs text-amber-700 dark:text-amber-300 mt-0.5">Vérifiez qu'Ollama est démarré dans <a href="/settings#providers" class="underline hover:no-underline">Paramètres</a></p>
            </div>
        </div>
        """
        html.append(error_block)
    
    if not all_procs:
        html.append("""
        <div class="bg-zinc-50 dark:bg-zinc-800/50 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800/50 border-dashed flex items-center justify-center text-zinc-400 text-sm">
           No models currently running.
        </div>
        """)
    
    for p in all_procs:
        name = escape(p.get("name", "?"))
        size = p.get("size", 0)
        size_gb = f"{size/1024/1024/1024:.1f} GB" if size else "-"
        provider = p.get("provider", "ollama")
        provider_name = p.get("provider_name", provider.title())
        
        # Provider badge colors
        if provider == "lmstudio":
            badge_class = "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400"
            indicator_color = "bg-teal-500 shadow-[0_0_8px_rgba(20,184,166,0.6)]"
        else:
            badge_class = "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
            indicator_color = "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"
        
        # Get quantization or context info
        if provider == "lmstudio":
            quant_info = p.get("quantization", "")
            arch = p.get("arch", "")
            ctx = p.get("context_length", 0)
            # Construire une info plus complète
            info_parts = []
            if quant_info:
                info_parts.append(quant_info)
            if arch:
                info_parts.append(arch)
            if ctx:
                info_parts.append(f"ctx:{ctx//1024}k")
            quant_info = " • ".join(info_parts) if info_parts else "LLM"
        else:
            quant_info = p.get('details', {}).get('quantization_level', 'Q4_K_M')
        
        # Calculate duration roughly if expires_at is present, or just show "Active"
        duration_text = "Active"
        
        # Eject button (only for Ollama models)
        eject_html = ""
        if provider == "ollama":
            eject_html = f"""
                     <form hx-post="/api/eject" hx-target="#running" hx-swap="outerHTML">
                        <input type="hidden" name="name" value="{name}"/>
                        <button class="rounded-lg border border-zinc-200 dark:border-zinc-700 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/10 dark:hover:text-red-400 px-2 py-1.5 text-xs transition-colors" title="Eject">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                        </button>
                     </form>
            """
        
        html.append(
            f"""
           <div class="bg-white dark:bg-zinc-900 rounded-2xl p-4 border border-zinc-200 dark:border-zinc-800 shadow-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div class="flex items-center gap-4">
                 <div class="w-2 h-2 rounded-full {indicator_color} flex-shrink-0"></div>
                 <div>
                    <div class="flex items-center gap-2">
                       <span class="font-semibold text-zinc-900 dark:text-zinc-100">{name}</span>
                       <span class="px-1.5 py-0.5 rounded text-[10px] font-bold {badge_class}">{escape(provider_name)}</span>
                    </div>
                    <div class="text-xs text-zinc-500 dark:text-zinc-400 font-mono">{escape(str(quant_info))}</div>
                 </div>
              </div>
              <div class="flex items-center gap-6 text-sm text-zinc-500 dark:text-zinc-400">
                 <div class="flex items-center gap-1.5">
                    <svg class="w-4 h-4 opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>
                    {size_gb}
                 </div>
                 <div class="flex items-center gap-1.5">
                    <svg class="w-4 h-4 opacity-70" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    {duration_text}
                 </div>
                 <div class="flex gap-2">
                     <a href="/chat?model={name}" class="rounded-lg bg-brand-50 hover:bg-brand-100 text-brand-600 dark:bg-brand-900/20 dark:text-brand-400 dark:hover:bg-brand-900/30 px-3 py-1.5 text-xs font-medium transition-colors flex items-center gap-1">
                        <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                        Chat
                     </a>
                     {eject_html}
                 </div>
              </div>
           </div>
            """
        )
    html.append("</div>")
    return Response("".join(html), mimetype="text/html")


@api_models_bp.post("/eject")
def eject() -> Response:
    name = request.values.get("name") or (request.json or {}).get("name")
    if not name:
        return jsonify({"error": "name requis"}), 400
    # gentle eject via generate keep_alive=0
    try:
        client().generate(prompt="", keep_alive=0, stream=False, model=name)
    except Exception:
        # Ignore errors here; UI will refresh list and user can use forced eject
        pass
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




@api_models_bp.get("/downloads/active")
@api_models_bp.get("/downloads/active")
def downloads_active() -> Response:
    # Fetch active downloads from Redis history
    active_jobs = []
    
    if getattr(current_app, "redis", None):
        try:
            # Get all history
            job_ids = current_app.redis.lrange("downloads:history", 0, -1)
            job_ids = [j.decode("utf-8") if isinstance(j, bytes) else j for j in job_ids]
            
            bus = ProgressBus(current_app.redis)
            
            for job_id in job_ids:
                # Check current status
                status = bus.get_last_status(job_id) or {}
                
                # Check if meta exists
                meta_raw = current_app.redis.get(f"job_meta:{job_id}")
                meta = {}
                if meta_raw:
                    try:
                        meta = json.loads(meta_raw)
                    except: pass
                
                # If no status but we have meta, use meta
                if not status and meta:
                    status = {"status": meta.get("status", "pending")}
                
                # Determine if active: not done and not error (unless recent?)
                # Actually, if done=True, it is not active.
                is_done = status.get("done") or status.get("error")
                
                if not is_done:
                    # Enrich status with meta name if missing
                    name = status.get("name") or meta.get("name") or "Unknown"
                    active_jobs.append({
                        "job_id": job_id,
                        "name": name,
                        "status": status,
                        "progress": status.get("progress", 0)
                    })
        except Exception as e:
            print(f"Error fetching active downloads: {e}")
            pass

    if not active_jobs:
        return Response("""
        <div class="bg-white dark:bg-zinc-900 rounded-2xl p-8 border border-zinc-200 dark:border-zinc-800 text-center space-y-3">
            <div class="w-12 h-12 bg-zinc-100 dark:bg-zinc-800 rounded-full flex items-center justify-center mx-auto text-zinc-400">
                <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
            </div>
            <p class="text-zinc-500 dark:text-zinc-400">No active downloads.</p>
        </div>
        """, mimetype="text/html")
        
    html = []
    for job in active_jobs:
        job_id = job["job_id"]
        name = escape(job["name"])
        progress = job["progress"]
        pct = int(progress * 100)
        status_text = escape(job["status"].get("status", "Starting..."))
        
        # Determine speed/size if available (mostly not available in simple status dict without extra logic)
        # We'll just show status text for now
        
        html.append(f"""
        <div class="bg-white dark:bg-zinc-900 rounded-2xl p-4 sm:p-6 border border-zinc-200 dark:border-zinc-800 shadow-card flex flex-col sm:flex-row sm:items-center gap-4" id="job-{job_id}" hx-get="/api/downloads/active" hx-select="#job-{job_id}" hx-trigger="every 1s" hx-swap="outerHTML">
            <div class="w-12 h-12 rounded-xl bg-blue-50 dark:bg-blue-900/20 text-blue-600 flex items-center justify-center flex-shrink-0">
                <div class="animate-bounce">
                    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                </div>
            </div>
            <div class="flex-1 min-w-0 space-y-2">
                <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 sm:gap-0">
                    <h3 class="font-semibold text-zinc-900 dark:text-zinc-100 truncate">{name}</h3>
                    <span class="text-sm font-medium text-brand-600">{status_text}</span>
                </div>
                <div class="w-full bg-zinc-100 dark:bg-zinc-800 rounded-full h-2 overflow-hidden">
                    <div class="bg-brand-600 h-full rounded-full transition-all duration-300" style="width: {pct}%"></div>
                </div>
                <!-- Optional: Speed estimate if we calculated it -->
            </div>
            <!-- Cancel button with custom modal -->
            <button type="button" 
                onclick="showConfirmDialog({{
                    title: 'Annuler le téléchargement',
                    message: 'Voulez-vous vraiment annuler le téléchargement de <strong>{name}</strong> ? Cette action est irréversible.',
                    type: 'danger',
                    confirmText: 'Annuler le téléchargement',
                    onConfirm: () => {{
                        htmx.ajax('POST', '/api/downloads/cancel/{job_id}', {{
                            target: '#active-downloads',
                            swap: 'innerHTML'
                        }});
                    }}
                }})"
                class="rounded-lg border border-zinc-200 dark:border-zinc-700 hover:bg-red-50 hover:text-red-600 hover:border-red-300 dark:hover:bg-red-900/10 dark:hover:text-red-400 dark:hover:border-red-700 px-3 py-2 text-xs transition-colors flex items-center gap-1.5 justify-center sm:justify-start w-full sm:w-auto" 
                title="Annuler le téléchargement">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span>Annuler</span>
            </button>
        </div>
        """)


        
    return Response("".join(html), mimetype="text/html")


@api_models_bp.get("/downloads/history")
def downloads_history() -> Response:
    history = []
    
    if getattr(current_app, "redis", None):
        try:
            job_ids = current_app.redis.lrange("downloads:history", 0, 49) # Last 50
            job_ids = [j.decode("utf-8") if isinstance(j, bytes) else j for j in job_ids]
            
            bus = ProgressBus(current_app.redis)
            
            for job_id in job_ids:
                status = bus.get_last_status(job_id) or {}
                
                meta_raw = current_app.redis.get(f"job_meta:{job_id}")
                meta = {}
                if meta_raw:
                    try: meta = json.loads(meta_raw)
                    except: pass
                
                # Check done state
                is_done = status.get("done") or status.get("error")
                
                # Only include finished jobs in history
                if is_done:
                    name = status.get("name") or meta.get("name") or "Unknown"
                    is_error = "error" in status
                    
                    # Try to get completion time
                    # We don't track completion time specifically in status, but we could infer or just say "Recently"
                    
                    history.append({
                        "name": name,
                        "status": status,
                        "error": is_error,
                        "time_ago": "Recently" # Placeholder
                    })
        except Exception:
            pass
            
    if not history:
        return Response("""
        <div class="p-8 text-center text-zinc-500 dark:text-zinc-400">No recent downloads.</div>
        """, mimetype="text/html")
        
    html = []
    for h in history:
        name = escape(h["name"])
        status_msg = escape(h["status"].get("error") if h["error"] else "Completed")
        time_ago = h["time_ago"]
        is_cancelled = h["status"].get("cancelled", False)
        
        # Déterminer l'icône et la couleur selon le statut
        if h["error"]:
            icon_color = "bg-red-50 dark:bg-red-900/20 text-red-600"
            icon_svg = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />'
        else:
            icon_color = "bg-green-50 dark:bg-green-900/20 text-green-600"
            icon_svg = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />'
        
        # Bouton Re-pull - visible pour les erreurs ou annulations, mais aussi disponible pour les succès
        repull_btn = f"""
            <form hx-post="/api/models/pull" hx-target="#active-downloads" hx-swap="beforeend" class="flex-shrink-0">
                <input type="hidden" name="name" value="{name}" />
                <button type="submit" 
                    class="rounded-lg border border-zinc-200 dark:border-zinc-700 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-300 dark:hover:bg-blue-900/10 dark:hover:text-blue-400 dark:hover:border-blue-700 px-3 py-1.5 text-xs transition-colors flex items-center gap-1.5"
                    title="Re-télécharger ce modèle">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <span>Re-pull</span>
                </button>
            </form>
        """
        
        html.append(f"""
        <div class="p-4 flex items-center gap-4 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 transition-colors border-b border-zinc-100 dark:border-zinc-800/50 last:border-0">
            <div class="w-10 h-10 rounded-lg {icon_color} flex items-center justify-center flex-shrink-0">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    {icon_svg}
                </svg>
            </div>
            <div class="flex-1 min-w-0">
                <div class="font-medium text-zinc-900 dark:text-zinc-100 truncate">{name}</div>
                <div class="text-xs text-zinc-500">{status_msg}</div>
            </div>
            <div class="text-xs text-zinc-400 flex-shrink-0">{time_ago}</div>
            {repull_btn}
        </div>
        """)
        
    return Response("".join(html), mimetype="text/html")


@api_models_bp.post("/downloads/clear")
def clear_downloads_history() -> Response:
    """Effacer l'historique des téléchargements terminés"""
    if not getattr(current_app, "redis", None):
        if request.headers.get("HX-Request"):
            return Response(
                "<div class='text-sm text-red-600 dark:text-red-400'>Redis non disponible</div>",
                mimetype="text/html"
            ), 500
        return jsonify({"error": "Redis non disponible"}), 500
    
    try:
        bus = ProgressBus(current_app.redis)
        
        # Récupérer tous les job_ids de l'historique
        job_ids = current_app.redis.lrange("downloads:history", 0, -1)
        job_ids = [j.decode("utf-8") if isinstance(j, bytes) else j for j in job_ids]
        
        # Ne supprimer que les jobs terminés (done ou error)
        jobs_to_remove = []
        for job_id in job_ids:
            status = bus.get_last_status(job_id) or {}
            is_done = status.get("done") or status.get("error")
            if is_done:
                jobs_to_remove.append(job_id)
                # Supprimer les métadonnées du job
                current_app.redis.delete(f"job_meta:{job_id}")
        
        # Supprimer les jobs terminés de la liste
        for job_id in jobs_to_remove:
            current_app.redis.lrem("downloads:history", 0, job_id)
        
        # Si c'est une requête HTMX, retourner l'historique mis à jour
        if request.headers.get("HX-Request"):
            return downloads_history()
        
        return jsonify({"success": True, "cleared": len(jobs_to_remove)})
    except Exception as e:
        if request.headers.get("HX-Request"):
            return Response(
                f"<div class='text-sm text-red-600 dark:text-red-400'>Erreur: {escape(str(e))}</div>",
                mimetype="text/html"
            ), 500
        return jsonify({"error": str(e)}), 500


@api_models_bp.post("/downloads/cancel/<job_id>")
def cancel_download(job_id: str) -> Response:
    """Annuler un téléchargement actif"""
    if not getattr(current_app, "redis", None):
        if request.headers.get("HX-Request"):
            return Response(
                "<div class='text-sm text-red-600 dark:text-red-400'>Redis non disponible</div>",
                mimetype="text/html"
            ), 500
        return jsonify({"error": "Redis non disponible"}), 500
    
    try:
        bus = ProgressBus(current_app.redis)
        
        # Publier un message d'annulation
        bus.publish(job_id, {
            "error": "Téléchargement annulé par l'utilisateur",
            "done": True,
            "cancelled": True
        })
        
        # Marquer le job comme annulé dans les métadonnées
        meta_raw = current_app.redis.get(f"job_meta:{job_id}")
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                meta["status"] = "cancelled"
                meta["cancelled_at"] = __import__("time").time()
                current_app.redis.setex(f"job_meta:{job_id}", 86400, json.dumps(meta))
            except Exception:
                pass
        
        # Si c'est une requête HTMX, retourner la liste mise à jour des téléchargements actifs
        if request.headers.get("HX-Request"):
            return downloads_active()
        
        return jsonify({"success": True, "message": "Téléchargement annulé"})
    except Exception as e:
        if request.headers.get("HX-Request"):
            return Response(
                f"<div class='text-sm text-red-600 dark:text-red-400'>Erreur: {escape(str(e))}</div>",
                mimetype="text/html"
            ), 500
        return jsonify({"error": str(e)}), 500


@api_models_bp.get("/models/trending-now")
def trending_models() -> Response:
    try:
        # Fetch trending models from ollama.com
        web_client = OllamaWebClient(timeout=5.0)
        # Search with empty query gets popular/trending
        results = web_client.search_models("")
        
        # Take top 3
        trending = results[:3]
        
        if not trending:
             return Response("<div class='text-zinc-500 text-sm'>Trending data unavailable.</div>", mimetype="text/html")
        
        html = []
        for m in trending:
             name = escape(m.get("name", "Unknown"))
             desc = escape(m.get("description", ""))
             # Truncate desc if too long
             if len(desc) > 60:
                 desc = desc[:60] + "..."
                 
             # Determine simple color/icon based on index or name hash for variety
             # Using simple cycle
             colors = [
                 ("bg-purple-50 dark:bg-purple-900/20", "text-purple-600"),
                 ("bg-blue-50 dark:bg-blue-900/20", "text-blue-600"),
                 ("bg-indigo-50 dark:bg-indigo-900/20", "text-indigo-600")
             ]
             # simple hash for color consistency
             c_idx = sum(ord(c) for c in name) % len(colors)
             bg_cls, text_cls = colors[c_idx]

             html.append(f"""
             <div class="bg-white dark:bg-zinc-900 rounded-2xl p-4 border border-zinc-200 dark:border-zinc-800 shadow-card hover:shadow-lg transition-shadow cursor-pointer flex items-center justify-between group">
               <div class="flex items-center gap-4">
                 <div class="w-10 h-10 rounded-xl {bg_cls} {text_cls} flex items-center justify-center">
                   <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                     <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                   </svg>
                 </div>
                 <div>
                   <div class="font-semibold text-zinc-900 dark:text-white flex items-center gap-2">
                     {name}
                     <span class="text-[10px] bg-orange-100 text-orange-600 px-1.5 rounded font-bold uppercase tracking-wide">Hot</span>
                   </div>
                   <div class="text-xs text-zinc-500 dark:text-zinc-400">{desc}</div>
                 </div>
               </div>
               <a href="https://ollama.com/library/{name}" target="_blank" class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors">
                   <svg class="w-5 h-5 text-zinc-300 group-hover:text-brand-600 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                     <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                   </svg>
               </a>
             </div>
             """)
        return Response("".join(html), mimetype="text/html")
    except Exception as e:
        return Response(f"<div class='text-red-500 text-sm'>Unavailable: {str(e)}</div>", mimetype="text/html")

