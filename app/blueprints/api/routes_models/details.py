from flask import request, Response, jsonify
from markupsafe import escape
from . import api_models_bp, client
from ....services.remote_search import model_details


@api_models_bp.post("/models/show")
def show_model() -> Response:
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

    err = None
    data = {}
    try:
        data = client().show(name)
    except Exception as e:
        err = str(e)

    accept = request.headers.get("Accept", "")
    if "text/html" in accept or request.headers.get("HX-Request"):
        details = []
        if isinstance(data, dict) and not err:
            modelfile = data.get("modelfile", "")
            parameters = data.get("parameters", "")
            template = data.get("template", "")
            details_data = data.get("details", {})
            license_text = data.get("license", "")

            digest = data.get("digest")
            size = details_data.get("size") if isinstance(details_data, dict) else data.get("size")
            format_type = details_data.get("format") if isinstance(details_data, dict) else None
            family = details_data.get("family") if isinstance(details_data, dict) else None
            families = details_data.get("families") if isinstance(details_data, dict) else None
            parameter_size = details_data.get("parameter_size") if isinstance(details_data, dict) else None
            quantization = details_data.get("quantization_level") if isinstance(details_data, dict) else None
            parent = data.get("parent_model")

            size_mb = f"{(size or 0)/1024/1024:.1f} Mo" if isinstance(size, (int, float)) else ""
            size_gb = f"{(size or 0)/1024/1024/1024:.2f} Go" if isinstance(size, (int, float)) and size > 1024*1024*1024 else ""

            details.append("<div class='space-y-3'>")
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

            if parameters:
                details.append("<div class='border-b border-zinc-200 dark:border-zinc-700 pb-2'>")
                details.append("<h3 class='font-medium text-sm mb-2'>Paramètres</h3>")
                details.append(f"<pre class='text-xs bg-zinc-100 dark:bg-zinc-900 p-2 rounded overflow-x-auto'>{escape(str(parameters))}</pre>")
                details.append("</div>")

            if template:
                template_preview = str(template)[:200] + ("..." if len(str(template)) > 200 else "")
                details.append("<div class='border-b border-zinc-200 dark:border-zinc-700 pb-2'>")
                details.append("<h3 class='font-medium text-sm mb-2'>Template</h3>")
                details.append(f"<pre class='text-xs bg-zinc-100 dark:bg-zinc-900 p-2 rounded overflow-x-auto'>{escape(template_preview)}</pre>")
                details.append("</div>")

            if license_text:
                license_preview = str(license_text)[:300] + ("..." if len(str(license_text)) > 300 else "")
                details.append("<div>")
                details.append("<h3 class='font-medium text-sm mb-2'>Licence</h3>")
                details.append(f"<pre class='text-xs bg-zinc-100 dark:bg-zinc-900 p-2 rounded overflow-x-auto whitespace-pre-wrap'>{escape(license_preview)}</pre>")
                details.append("</div>")

            details.append("</div>")

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
    err = None
    data = {}
    try:
        data = client().show(name)
    except Exception as e:
        err = str(e)

    if err:
        return Response(
            f"""<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 text-center">
                <h3 class="text-lg font-semibold text-red-700 dark:text-red-300 mb-2">Erreur de chargement</h3>
                <p class="text-red-600 dark:text-red-400">{escape(err)}</p>
            </div>""",
            mimetype="text/html"
        )

    details_data = data.get("details", {}) if isinstance(data, dict) else {}
    size = data.get("size") or details_data.get("size") or 0
    digest_raw = data.get("digest", "")

    if not size or not digest_raw:
        try:
            tags_data = client().tags()
            models_list = tags_data.get("models", []) if isinstance(tags_data, dict) else []
            for m in models_list:
                if m.get("name") == name:
                    if not size: size = m.get("size", 0)
                    if not digest_raw: digest_raw = m.get("digest", "")
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

    arch_badges = ""
    if families:
        for f in families:
            arch_badges += f'<span class="text-xs bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-300 px-2 py-1 rounded-lg">{escape(f)}</span> '
    else:
        arch_badges = '<span class="text-zinc-400">-</span>'

    parent_row = ""
    if parent:
        parent_row = f"""
                <div class="px-6 py-4 flex justify-between items-center">
                    <span class="text-zinc-500 dark:text-zinc-400">Modèle parent</span>
                    <span class="font-mono text-sm bg-zinc-100 dark:bg-zinc-800 px-3 py-1 rounded-lg">{escape(parent)}</span>
                </div>"""

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

    template_content = escape(template) if template else "Aucun template défini"
    license_content = escape(license_text) if license_text else "Aucune licence disponible"

    html = _build_details_page(
        name, parameter_size, size_gb, quantization, family, format_type, digest,
        parent_row, arch_badges, system_section, params_section,
        template_content, license_content
    )
    return Response(html, mimetype="text/html")


def _build_details_page(name, parameter_size, size_gb, quantization, family,
                        format_type, digest, parent_row, arch_badges,
                        system_section, params_section, template_content, license_content):
    """Build the full model details HTML page."""
    return f"""
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-5">
            <div class="flex items-center gap-3 mb-3">
                <div class="p-2.5 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                    <svg class="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>
                </div>
                <span class="text-sm text-zinc-500 dark:text-zinc-400">Paramètres</span>
            </div>
            <div class="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{escape(str(parameter_size))}</div>
        </div>
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-5">
            <div class="flex items-center gap-3 mb-3">
                <div class="p-2.5 bg-purple-50 dark:bg-purple-900/20 rounded-xl">
                    <svg class="w-5 h-5 text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" /></svg>
                </div>
                <span class="text-sm text-zinc-500 dark:text-zinc-400">Taille</span>
            </div>
            <div class="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{escape(size_gb)}</div>
        </div>
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-5">
            <div class="flex items-center gap-3 mb-3">
                <div class="p-2.5 bg-emerald-50 dark:bg-emerald-900/20 rounded-xl">
                    <svg class="w-5 h-5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                </div>
                <span class="text-sm text-zinc-500 dark:text-zinc-400">Quantification</span>
            </div>
            <div class="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{escape(str(quantization))}</div>
        </div>
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-5">
            <div class="flex items-center gap-3 mb-3">
                <div class="p-2.5 bg-orange-50 dark:bg-orange-900/20 rounded-xl">
                    <svg class="w-5 h-5 text-orange-600 dark:text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" /></svg>
                </div>
                <span class="text-sm text-zinc-500 dark:text-zinc-400">Famille</span>
            </div>
            <div class="text-2xl font-bold text-zinc-900 dark:text-zinc-100">{escape(str(family))}</div>
        </div>
    </div>

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
                    <div class="flex flex-wrap gap-2 justify-end">{arch_badges}</div>
                </div>
            </div>
        </div>
        {system_section}
        {params_section}
    </div>

    <div x-show="activeTab === 'template'" style="display: none;" class="space-y-6">
        <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
            <div class="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between">
                <h3 class="font-semibold text-zinc-900 dark:text-zinc-100">Template de prompt</h3>
                <button onclick="navigator.clipboard.writeText(document.getElementById('template-content').textContent)"
                        class="text-sm text-brand-600 hover:text-brand-500 flex items-center gap-1">
                    Copier
                </button>
            </div>
            <div class="p-6">
                <pre id="template-content" class="text-sm bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl overflow-x-auto whitespace-pre-wrap font-mono text-zinc-700 dark:text-zinc-300 max-h-96 overflow-y-auto">{template_content}</pre>
            </div>
        </div>
    </div>

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

    <div x-show="activeTab === 'actions'" style="display: none;" class="space-y-6">
        <div class="grid gap-4 sm:grid-cols-2">
            <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6">
                <h4 class="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Mettre à jour</h4>
                <form hx-post="/api/models/pull" hx-target="#action-out" hx-swap="innerHTML">
                    <input type="hidden" name="name" value="{escape(name)}"/>
                    <button type="submit" class="w-full px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium transition-all">Lancer la mise à jour</button>
                </form>
            </div>
            <div class="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6">
                <h4 class="font-semibold text-zinc-900 dark:text-zinc-100 mb-4">Copier / Renommer</h4>
                <form hx-post="/api/models/copy" hx-target="#action-out" hx-swap="innerHTML" class="flex gap-2">
                    <input type="hidden" name="source" value="{escape(name)}"/>
                    <input type="text" name="dest" placeholder="nouveau-nom:tag"
                           class="flex-1 px-4 py-2.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 focus:ring-2 focus:ring-brand-500/20"/>
                    <button type="submit" class="px-4 py-2.5 rounded-xl bg-green-600 hover:bg-green-500 text-white font-medium transition-all">Copier</button>
                </form>
            </div>
        </div>
    </div>
    """
