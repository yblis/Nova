from flask import request, current_app, Response, jsonify
from markupsafe import escape
from . import api_models_bp, client
from ....services.ollama_web import OllamaWebClient


@api_models_bp.get("/stats")
def stats() -> Response:
    try:
        client_inst = client()
        models_data = client_inst.tags()
        models_list = models_data.get("models", []) if isinstance(models_data, dict) else []

        ps_data = client_inst.ps()
        running_list = ps_data.get("models", []) if isinstance(ps_data, dict) else []

        total_models = len(models_list)
        active_models = len(running_list)

        lmstudio_active = 0
        try:
            from ....services.provider_manager import get_provider_manager
            from ....services.llm_clients.openai_compatible_client import OpenAICompatibleClient

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
        total_size = sum(m.get("size", 0) for m in models_list)
        vram_usage = sum(m.get("size", 0) for m in running_list)

        def fmt_size(b):
            if b >= 1024**3: return f"{b/1024**3:.1f} GB"
            if b >= 1024**2: return f"{b/1024**2:.0f} MB"
            return f"{b} B"

        html = f"""
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
    except Exception:
        error_html = """
        <div class="col-span-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-2xl p-6 text-center">
            <div class="mx-auto w-12 h-12 bg-amber-100 dark:bg-amber-900/30 rounded-xl flex items-center justify-center mb-3">
                <svg class="w-6 h-6 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            </div>
            <h3 class="font-semibold text-amber-800 dark:text-amber-200 mb-1">Ollama indisponible</h3>
            <p class="text-sm text-amber-700 dark:text-amber-300 mb-3">Impossible de se connecter à Ollama.</p>
            <a href="/settings#providers" class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm font-medium transition-colors">
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
        return Response(str(len(items)), mimetype="text/plain")
    except Exception:
        return Response("0", mimetype="text/plain")


@api_models_bp.get("/running")
def running() -> Response:
    error = None
    procs = []
    lmstudio_procs = []

    try:
        data = client().ps()
        procs = data.get("models", []) if isinstance(data, dict) else []
        for p in procs:
            p["provider"] = "ollama"
    except Exception as e:
        error = str(e)

    try:
        from ....services.provider_manager import get_provider_manager
        from ....services.llm_clients.openai_compatible_client import OpenAICompatibleClient

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
                        for m in loaded:
                            m["provider"] = "lmstudio"
                            m["provider_name"] = provider.get("name", "LM Studio")
                        lmstudio_procs.extend(loaded)
                    except Exception as lm_err:
                        current_app.logger.warning(f"Failed to get LM Studio models: {lm_err}")
    except Exception as e:
        current_app.logger.warning(f"Failed to check LM Studio providers: {e}")

    all_procs = procs + lmstudio_procs
    html = ['<div id="running" hx-get="/api/running" hx-trigger="every 5s" hx-target="#running" hx-swap="outerHTML" class="space-y-3">']

    count = len(all_procs)
    html.append(f"<span id='running-count' hx-swap-oob='true' class='text-brand-600 font-bold'>{count}</span>")

    if error and not lmstudio_procs:
        html.append("""
        <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 flex items-start gap-3">
            <svg class="w-5 h-5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
                <p class="text-sm font-medium text-amber-800 dark:text-amber-200">Ollama indisponible</p>
                <p class="text-xs text-amber-700 dark:text-amber-300 mt-0.5">Vérifiez qu'Ollama est démarré dans <a href="/settings#providers" class="underline hover:no-underline">Paramètres</a></p>
            </div>
        </div>
        """)

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

        if provider == "lmstudio":
            badge_class = "bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400"
            indicator_color = "bg-teal-500 shadow-[0_0_8px_rgba(20,184,166,0.6)]"
        else:
            badge_class = "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
            indicator_color = "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"

        if provider == "lmstudio":
            quant_info = p.get("quantization", "")
            arch = p.get("arch", "")
            ctx = p.get("context_length", 0)
            info_parts = []
            if quant_info: info_parts.append(quant_info)
            if arch: info_parts.append(arch)
            if ctx: info_parts.append(f"ctx:{ctx//1024}k")
            quant_info = " • ".join(info_parts) if info_parts else "LLM"
        else:
            quant_info = p.get('details', {}).get('quantization_level', 'Q4_K_M')

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
        elif provider == "lmstudio":
            eject_html = f"""
                     <button hx-post="/api/models/unload" hx-vals='{{"model": "{name}"}}' hx-target="#running" hx-swap="outerHTML"
                             class="rounded-lg border border-zinc-200 dark:border-zinc-700 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/10 dark:hover:text-red-400 px-2 py-1.5 text-xs transition-colors" title="Eject">
                         <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                     </button>
            """

        html.append(f"""
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
                    Active
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
        """)

    html.append("</div>")
    return Response("".join(html), mimetype="text/html")


@api_models_bp.get("/models/recent")
def recent_models() -> Response:
    try:
        from datetime import datetime
        client_inst = client()
        models_data = client_inst.tags()
        items = models_data.get("models", []) if isinstance(models_data, dict) else []

        items.sort(key=lambda x: x.get("modified_at", ""), reverse=True)
        recent = items[:3]

        if not recent:
            return Response("<div class='text-zinc-500 text-sm'>No models installed.</div>", mimetype="text/html")

        html = []
        for m in recent:
            name = escape(m.get("name", "?"))
            modified = m.get("modified_at", "")
            date_str = "Unknown"
            if modified:
                try:
                    dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                    delta = datetime.now(dt.tzinfo) - dt
                    if delta.days > 0:
                        date_str = f"{delta.days} days ago"
                    else:
                        hours = delta.seconds // 3600
                        if hours > 0: date_str = f"{hours} hours ago"
                        else: date_str = f"{delta.seconds // 60} minutes ago"
                except Exception:
                    pass

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
    except Exception:
        return Response("""
        <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 text-center">
            <p class="text-sm font-medium text-amber-800 dark:text-amber-200">Ollama indisponible</p>
            <p class="text-xs text-amber-700 dark:text-amber-300 mt-1">Vérifiez qu'Ollama est démarré</p>
        </div>
        """, mimetype="text/html")


@api_models_bp.get("/models/trending-now")
def trending_models() -> Response:
    try:
        web_client = OllamaWebClient(timeout=5.0)
        results = web_client.search_models("")
        trending = results[:3]

        if not trending:
            return Response("<div class='text-zinc-500 text-sm'>Trending data unavailable.</div>", mimetype="text/html")

        html = []
        colors = [
            ("bg-purple-50 dark:bg-purple-900/20", "text-purple-600"),
            ("bg-blue-50 dark:bg-blue-900/20", "text-blue-600"),
            ("bg-indigo-50 dark:bg-indigo-900/20", "text-indigo-600")
        ]

        for m in trending:
            name = escape(m.get("name", "Unknown"))
            desc = escape(m.get("description", ""))
            if len(desc) > 60:
                desc = desc[:60] + "..."
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
