import re
from flask import request, Response, jsonify
from markupsafe import escape
from ....extensions import cache
from . import api_models_bp, client, models_cache_key, detect_model_capabilities
from ....services.model_metadata_service import get_model_metadata


@api_models_bp.get("/models")
@cache.cached(timeout=10, key_prefix=models_cache_key)
def list_models() -> Response:
    q = (request.args.get("q") or "").strip().lower()
    view = request.args.get("view")

    items = []
    error = None
    provider_type = "ollama"
    provider_name = "Ollama"

    try:
        from ....services.provider_manager import get_provider_manager
        mgr = get_provider_manager()
        active_provider = mgr.get_active_provider()

        if active_provider and active_provider.get("type") == "lmstudio":
            provider_type = "lmstudio"
            provider_name = active_provider.get("name", "LM Studio")

            from ....services.llm_clients.openai_compatible_client import OpenAICompatibleClient
            full_provider = mgr.get_provider(active_provider["id"], include_api_key=True)
            if full_provider and full_provider.get("url"):
                lm_client = OpenAICompatibleClient(
                    provider_type="lmstudio",
                    base_url=full_provider.get("url"),
                    api_key=full_provider.get("api_key", "")
                )
                lm_models = lm_client.list_models()
                for m in lm_models:
                    param_size = m.get("params_string", "")
                    if not param_size:
                        ctx = m.get("max_context_length", 0)
                        param_size = f"{ctx//1024}k" if ctx else "-"

                    size_bytes = m.get("size_bytes", 0)
                    capabilities = m.get("capabilities", {})
                    detected_caps = []
                    if m.get("supports_vision") or (isinstance(capabilities, dict) and capabilities.get("vision")):
                        detected_caps.append("vision")
                    if m.get("supports_tools") or (isinstance(capabilities, dict) and capabilities.get("trained_for_tool_use")):
                        detected_caps.append("tools")
                    if m.get("type") == "embedding":
                        detected_caps.append("embedding")

                    items.append({
                        "name": m.get("id", m.get("name", "?")),
                        "size": size_bytes,
                        "details": {
                            "family": m.get("arch", "-"),
                            "quantization_level": m.get("quantization", "-"),
                            "parameter_size": param_size,
                            "format": m.get("format", ""),
                            "capabilities": detected_caps
                        },
                        "state": m.get("state", "not-loaded"),
                        "type": m.get("type", "llm"),
                        "publisher": m.get("publisher", ""),
                        "display_name": m.get("display_name", ""),
                        "api_version": m.get("api_version", ""),
                        "provider": "lmstudio"
                    })
        else:
            data = client().tags()
            items = data.get("models", []) if isinstance(data, dict) else data
            for m in items:
                m["provider"] = "ollama"
    except Exception as e:
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

    if request.headers.get("Accept") == "application/json" and not request.headers.get("HX-Request"):
        return jsonify({"models": items})

    if view == "list":
        return _render_list_view(items, error)

    return _render_grid_view(items, error)


def _render_list_view(items, error):
    html = []
    if error:
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

        if provider == "lmstudio":
            provider_badge = '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400">LM Studio</span>'
            state_badge = '<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">● Loaded</span>' if model_state == "loaded" else ''
        else:
            provider_badge = ''
            state_badge = ''

        model_name_raw = m.get("name", "")
        metadata = get_model_metadata(model_name_raw)
        if metadata:
            capabilities = metadata.get("capabilities", [])
            if metadata.get("parameter_size"):
                param_size = escape(metadata.get("parameter_size"))
        else:
            capabilities = detect_model_capabilities(model_name_raw, details)

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
        badges_html = f'{provider_badge} {state_badge} {badges_html}'

        if provider == "lmstudio":
            stop_button = ""
            if model_state == "loaded":
                stop_button = f'''
                  <button class="p-2 rounded-lg text-zinc-400 hover:text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-900/20 transition-colors" title="Stop (décharger le modèle)"
                          hx-post="/api/models/unload" hx-vals='{{"model": "{name}"}}' hx-target="#toast-container" hx-swap="beforeend">
                      <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><rect x="6" y="6" width="12" height="12" rx="1" stroke-width="2"/></svg>
                  </button>
                '''
            actions_html = f"""
                  <a href="/chat?model={name}" class="p-2 rounded-lg text-zinc-400 hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors" title="Chat">
                     <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                  </a>
                  {stop_button}
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


def _render_grid_view(items, error):
    html = ['<div id="models" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">']
    if error:
        html.append("""
        <div class="sm:col-span-2 xl:col-span-3">
            <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-2xl p-6 text-center">
                <h3 class="font-semibold text-amber-800 dark:text-amber-200 mb-1">Ollama indisponible</h3>
                <p class="text-sm text-amber-700 dark:text-amber-300 mb-3">Vérifiez qu'Ollama est démarré ou configurez-le.</p>
                <a href="/settings#providers" class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium transition-colors">
                    Configurer Ollama
                </a>
            </div>
        </div>
        """)
    if not items:
        html.append('<div class="sm:col-span-2 xl:col-span-3"><p class="text-sm text-slate-500 dark:text-zinc-400">Aucun modèle.</p></div>')

    for m in items:
        raw_name = m.get("name", "?")
        name = escape(raw_name)
        safe_id = "pull-" + re.sub(r"[^a-zA-Z0-9_-]", "-", str(raw_name))
        size = m.get("size", 0)
        size_mb = f"{size/1024/1024:.1f} Mo" if isinstance(size, (int, float)) else ""
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
            <div class="group bg-white dark:bg-zinc-800 rounded-xl shadow-card p-4 flex flex-col gap-3 border border-zinc-200 dark:border-zinc-700">
              <div class="flex items-start justify-between">
                <div>
                  <a class="font-semibold text-zinc-900 dark:text-zinc-100 hover:text-brand-700 dark:hover:text-brand-400" href="/models/{name}">{name}</a>
                  <div class="text-xs text-zinc-500 dark:text-zinc-400">{size_mb}</div>
                  <div class="text-xs text-zinc-500 dark:text-zinc-400">{date_str}</div>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <form hx-post="/api/models/pull" hx-target="#{safe_id}" class="inline">
                  <input type="hidden" name="name" value="{name}"/>
                  <button class="text-sm rounded-lg bg-brand-600 hover:bg-brand-500 text-white px-3 py-1.5">Mettre à jour</button>
                </form>
                <a href="/models/{name}/edit" class="text-sm rounded-lg border border-purple-300 dark:border-purple-600 text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/20 px-3 py-1.5">Modifier</a>
                <a href="/models/{name}" class="text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-50 dark:hover:bg-zinc-700 px-3 py-1.5">Détails</a>
              </div>
              <div id="{safe_id}" class="text-xs text-zinc-500 dark:text-zinc-400"></div>
            </div>
            """.replace("{name}", str(name)).replace("{size_mb}", str(size_mb)).replace("{safe_id}", str(safe_id)).replace("{date_str}", str(date_str))
        )
    html.append("</div>")
    return Response("".join(html), mimetype="text/html")
