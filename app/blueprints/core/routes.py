from __future__ import annotations

import os
from flask import Blueprint, render_template, current_app, send_from_directory, request


core_bp = Blueprint(
    "core",
    __name__,
    template_folder="templates",
    static_folder="static",
)


@core_bp.route("/")
def index():
    return render_template(
        "index.html",
        ollama_base_url=current_app.config.get("OLLAMA_BASE_URL"),
    )


@core_bp.route("/models")
def models():
    return render_template("models.html")


@core_bp.route("/models/<name>")
def model_detail(name: str):
    return render_template("model_detail.html", name=name)


@core_bp.route("/models/<name>/edit")
def model_edit(name: str):
    return render_template("model_edit.html", name=name)


@core_bp.route("/search")
def search():
    return render_template("search.html")


@core_bp.route("/discover")
def discover():
    return render_template("discover.html")  # Renamed from huggingface.html


@core_bp.route("/huggingface")
def huggingface():
    # Redirect or keep for backward compatibility, but render discover
    return render_template("discover.html")


@core_bp.route("/chat")
def chat():
    return render_template("chat.html")


@core_bp.route("/texts")
def texts_page():
    """
    Texts tool page with dynamic content.
    The tool selection is managed client-side via Alpine.js and URL hash.
    """
    return render_template("texts.html")


@core_bp.route("/specialists")
@core_bp.route("/specialists/<specialist_slug>")
def specialists_page(specialist_slug=None):
    """
    Specialists page for creating AI assistants with custom knowledge.
    The specialist_slug in URL is the slugified name, handled client-side by Alpine.js.
    """
    return render_template("specialists.html")


@core_bp.route("/downloads")
def downloads():
    return render_template("downloads.html")


# ============== SPA Partials Routes ==============

@core_bp.route("/partials/<page>")
def spa_partial(page: str):
    """
    Retourne uniquement le contenu sans base.html.
    Utilisé par le routeur SPA pour le chargement dynamique.
    Utilise le template principal avec ajax.html comme layout.
    """
    from flask import abort
    
    valid_pages = ["index", "models", "discover", "downloads", "chat", "texts", "settings", "specialists"]
    
    if page not in valid_pages:
        abort(404)
    
    return render_template(f"{page}.html", layout_template="ajax.html")


@core_bp.route("/settings")
@core_bp.route("/settings/<page>")
def settings_page(page: str = "general"):
    """
    Settings page with dynamic content.
    The tab selection is managed client-side via Alpine.js and URL hash.
    """
    return render_template("settings.html")


@core_bp.route("/manifest.json")
def manifest():
    pwa_dir = os.path.join(current_app.root_path, "pwa")
    return send_from_directory(pwa_dir, "manifest.json", mimetype="application/json")


@core_bp.route("/service-worker.js")
def service_worker():
    # Service worker must be served from the root scope
    pwa_dir = os.path.join(current_app.root_path, "pwa")
    response = send_from_directory(pwa_dir, "service-worker.js", mimetype="application/javascript")
    # Ensure no caching issues while developing; production should version cache names
    response.headers["Cache-Control"] = "no-cache"
    return response


# Templates


@core_bp.route("/health")
def health():
    from ...services.ollama_client import OllamaClient
    from ...utils import get_effective_ollama_base_url
    
    ok = True
    details = {}
    
    # Check Redis
    try:
        current_app.redis.ping()  # type: ignore[attr-defined]
        details["redis"] = True
    except Exception:
        details["redis"] = False
        ok = False
    
    # Check Ollama
    try:
        client = OllamaClient(
            base_url=get_effective_ollama_base_url(),
            connect_timeout=5,
            read_timeout=10,
        )
        client.tags()
        details["ollama"] = True
    except Exception as e:
        details["ollama"] = False
        details["ollama_error"] = str(e)
        ok = False
    
    return {"ok": ok, **details}
