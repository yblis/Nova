import json
from flask import request, current_app, Response, jsonify
from markupsafe import escape
from . import api_models_bp
from ....services.progress_bus import ProgressBus


@api_models_bp.get("/downloads/active")
def downloads_active() -> Response:
    active_jobs = []

    if getattr(current_app, "redis", None):
        try:
            job_ids = current_app.redis.lrange("downloads:history", 0, -1)
            job_ids = [j.decode("utf-8") if isinstance(j, bytes) else j for j in job_ids]
            bus = ProgressBus(current_app.redis)

            for job_id in job_ids:
                status = bus.get_last_status(job_id) or {}
                meta_raw = current_app.redis.get(f"job_meta:{job_id}")
                meta = {}
                if meta_raw:
                    try:
                        meta = json.loads(meta_raw)
                    except Exception:
                        pass

                if not status and meta:
                    status = {"status": meta.get("status", "pending")}

                is_done = status.get("done") or status.get("error")
                if not is_done:
                    name = status.get("name") or meta.get("name") or "Unknown"
                    active_jobs.append({
                        "job_id": job_id,
                        "name": name,
                        "status": status,
                        "progress": status.get("progress", 0)
                    })
        except Exception as e:
            print(f"Error fetching active downloads: {e}")

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
            </div>
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
            job_ids = current_app.redis.lrange("downloads:history", 0, 49)
            job_ids = [j.decode("utf-8") if isinstance(j, bytes) else j for j in job_ids]
            bus = ProgressBus(current_app.redis)

            for job_id in job_ids:
                status = bus.get_last_status(job_id) or {}
                meta_raw = current_app.redis.get(f"job_meta:{job_id}")
                meta = {}
                if meta_raw:
                    try:
                        meta = json.loads(meta_raw)
                    except Exception:
                        pass

                is_done = status.get("done") or status.get("error")
                if is_done:
                    name = status.get("name") or meta.get("name") or "Unknown"
                    is_error = "error" in status
                    history.append({
                        "name": name,
                        "status": status,
                        "error": is_error,
                        "time_ago": "Recently"
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

        if h["error"]:
            icon_color = "bg-red-50 dark:bg-red-900/20 text-red-600"
            icon_svg = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />'
        else:
            icon_color = "bg-green-50 dark:bg-green-900/20 text-green-600"
            icon_svg = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />'

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
        job_ids = current_app.redis.lrange("downloads:history", 0, -1)
        job_ids = [j.decode("utf-8") if isinstance(j, bytes) else j for j in job_ids]

        jobs_to_remove = []
        for job_id in job_ids:
            status = bus.get_last_status(job_id) or {}
            is_done = status.get("done") or status.get("error")
            if is_done:
                jobs_to_remove.append(job_id)
                current_app.redis.delete(f"job_meta:{job_id}")

        for job_id in jobs_to_remove:
            current_app.redis.lrem("downloads:history", 0, job_id)

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
        bus.publish(job_id, {
            "error": "Téléchargement annulé par l'utilisateur",
            "done": True,
            "cancelled": True
        })

        meta_raw = current_app.redis.get(f"job_meta:{job_id}")
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
                meta["status"] = "cancelled"
                meta["cancelled_at"] = __import__("time").time()
                current_app.redis.setex(f"job_meta:{job_id}", 86400, json.dumps(meta))
            except Exception:
                pass

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
