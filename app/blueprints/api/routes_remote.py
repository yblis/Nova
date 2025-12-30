from __future__ import annotations

import re
from flask import Blueprint, request, jsonify, Response
from ...services.remote_search import search_models, model_variants
from markupsafe import escape


api_remote_bp = Blueprint("api_remote", __name__)


@api_remote_bp.get("/remote/search")
def remote_search() -> Response:
    q = (request.args.get("q") or "").strip()
    items = search_models(q)
    # Render lightweight HTML for HTMX result list
    html = ["<div id=\"remote-results\" class=\"grid gap-4 sm:grid-cols-2 xl:grid-cols-3\">"]
    if not items:
        html.append("<div class=\"sm:col-span-2 xl:col-span-3\"><p class=\"text-sm text-slate-500\">Aucun résultat.</p></div>")
    for obj in items:
        raw_name = obj.get("name", "")
        name_html = escape(raw_name)
        safe_id = "pull-" + re.sub(r"[^a-zA-Z0-9_-]", "-", str(raw_name))
        variants_id = "variants-" + re.sub(r"[^a-zA-Z0-9_-]", "-", str(raw_name))
        details_id = "details-" + safe_id
        card: list[str] = []
        card.append("<div class='bg-white dark:bg-zinc-800 rounded-xl shadow-card p-4 border border-zinc-200 dark:border-zinc-700'>")
        card.append(f"<div class='font-semibold text-zinc-900 dark:text-zinc-100'>{name_html}</div>")
        controls = []
        controls.append(
            f"<button class='text-sm rounded-lg bg-brand-600 hover:bg-brand-500 text-white px-3 py-1.5' "
            f"hx-get='/api/remote/variants?model={name_html}' hx-target='#" + variants_id + "' hx-swap='outerHTML'>Variantes</button>"
        )
        controls.append(
            f"<form hx-post='/api/models/pull' hx-target='#{safe_id}' class='inline'>"
            f"<input type='hidden' name='name' value='{name_html}'/>"
            f"<button class='text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-50 dark:hover:bg-zinc-700 px-3 py-1.5'>Pull (défaut)</button>"
            f"</form>"
        )
        controls.append(
            f"<form hx-post='/api/models/show' hx-target='#" + details_id + "' hx-swap='innerHTML' class='inline'>"
            f"<input type='hidden' name='name' value='{name_html}'/>"
            f"<button class='text-sm rounded-lg border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-50 dark:hover:bg-zinc-700 px-3 py-1.5'>Détails</button>"
            f"</form>"
        )
        card.append("<div class='mt-2 flex flex-wrap items-center gap-2'>" + "".join(controls) + "</div>")
        card.append(f"<div id='{safe_id}' class='text-xs text-zinc-500 dark:text-zinc-400 mt-1'></div>")
        card.append(f"<div id='{variants_id}' class='mt-3 text-sm text-zinc-600 dark:text-zinc-300'></div>")
        card.append(f"<div id='{details_id}' class='mt-3'></div>")
        card.append("</div>")
        html.append("".join(card))
    html.append("</div>")
    return Response("".join(html), mimetype="text/html")


@api_remote_bp.get("/remote/variants")
def remote_variants() -> Response:
    model = (request.args.get("model") or request.values.get("model") or "").strip()
    if not model:
        variants_id = "variants-unknown"
        return Response(
            f"<div id='{variants_id}' class='text-sm text-red-600 dark:text-red-400'>Paramètre model manquant</div>",
            mimetype="text/html"
        ), 400
    tags = model_variants(model)
    variants_id = "variants-" + re.sub(r"[^a-zA-Z0-9_-]", "-", model)
    safe_id = "pull-" + re.sub(r"[^a-zA-Z0-9_-]", "-", model)
    if not tags:
        return Response(f"<div id='{variants_id}' class='text-sm text-zinc-600 dark:text-zinc-300'>Aucune variante trouvée.</div>", mimetype="text/html")
    html = [f"<div id='{variants_id}' class='flex flex-col gap-2'>"]
    html.append("<div class='text-xs text-zinc-500 dark:text-zinc-400'>Sélectionnez une variante pour Pull ou voir les détails.</div>")
    html.append("<div class='flex flex-wrap gap-2'>")
    for t in tags:
        tag = escape(t)
        full = f"{model}:{t}"
        html.append(
            f"<div class='flex items-center gap-2'>"
            f"<form hx-post='/api/models/pull' hx-target='#{safe_id}' class='inline'>"
            f"<input type='hidden' name='name' value='{escape(full)}'/>"
            f"<button class='text-xs rounded-full bg-brand-600 hover:bg-brand-500 text-white px-3 py-1'>Pull {tag}</button>"
            f"</form>"
            f"<a href='/models/{escape(full)}' class='text-xs rounded-full border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-50 dark:hover:bg-zinc-700 px-3 py-1'>Détails</a>"
            f"</div>"
        )
    html.append("</div>")
    html.append("</div>")
    return Response("".join(html), mimetype="text/html")
