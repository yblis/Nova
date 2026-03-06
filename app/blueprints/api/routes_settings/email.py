from flask import jsonify, request
from . import api_settings_bp


@api_settings_bp.get("/email/config")
def get_email_config():
    """Récupère la configuration de l'agent email."""
    from ....services.email import get_config, is_email_available
    config = get_config()
    config["is_available"] = is_email_available()
    return jsonify(config)


@api_settings_bp.post("/email/config")
def set_email_config():
    """Configure les paramètres de l'agent email."""
    from ....services.email import set_config
    data = request.get_json(silent=True) or {}
    updates = {}

    for field in ["imap_host", "smtp_host", "pop3_host", "email_address", "default_folder",
                   "auth_type", "reception_protocol", "imap_encryption", "smtp_encryption",
                   "pop3_encryption", "oauth2_client_id"]:
        if field in data:
            updates[field] = str(data[field]).strip()

    if "password" in data and data["password"]:
        updates["password"] = data["password"]
    if "oauth2_client_secret" in data and data["oauth2_client_secret"]:
        updates["oauth2_client_secret"] = data["oauth2_client_secret"]

    for port_field in ["imap_port", "smtp_port", "pop3_port"]:
        if port_field in data:
            try:
                port = int(data[port_field])
                if 1 <= port <= 65535:
                    updates[port_field] = port
                else:
                    return jsonify({"error": f"{port_field} doit être entre 1 et 65535"}), 400
            except (ValueError, TypeError):
                return jsonify({"error": f"{port_field} invalide"}), 400

    if "max_emails" in data:
        try:
            max_emails = int(data["max_emails"])
            if 1 <= max_emails <= 50:
                updates["max_emails"] = max_emails
            else:
                return jsonify({"error": "max_emails doit être entre 1 et 50"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "max_emails invalide"}), 400

    if "timeout" in data:
        try:
            timeout = int(data["timeout"])
            if 5 <= timeout <= 60:
                updates["timeout"] = timeout
            else:
                return jsonify({"error": "timeout doit être entre 5 et 60 secondes"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "timeout invalide"}), 400

    for bool_field in ["auto_summarize", "include_attachments_info"]:
        if bool_field in data:
            updates[bool_field] = bool(data[bool_field])

    if updates:
        success = set_config(updates)
        if not success:
            return jsonify({"error": "Échec de la sauvegarde"}), 500

    return jsonify({"ok": True})


@api_settings_bp.post("/email/test")
def test_email_connection():
    """Teste la connexion réception (IMAP/POP3) et SMTP."""
    from ....services.email import _get_imap_connection, _get_smtp_connection, _get_pop3_connection, _load_config

    config = _load_config()
    protocol = config.get("reception_protocol", "imap")
    results = {"reception_ok": False, "smtp_ok": False, "reception_message": "", "smtp_message": "", "protocol": protocol}

    try:
        if protocol == "pop3":
            pop3 = _get_pop3_connection()
            num_messages, _ = pop3.stat()
            pop3.quit()
            results["reception_ok"] = True
            results["reception_message"] = f"POP3 OK ({num_messages} messages)"
        else:
            imap = _get_imap_connection()
            imap.logout()
            results["reception_ok"] = True
            results["reception_message"] = "IMAP OK"
    except Exception as e:
        results["reception_message"] = str(e)

    try:
        smtp = _get_smtp_connection()
        smtp.quit()
        results["smtp_ok"] = True
        results["smtp_message"] = "SMTP OK"
    except Exception as e:
        results["smtp_message"] = str(e)

    ok = results["reception_ok"] and results["smtp_ok"]
    proto_label = "POP3" if protocol == "pop3" else "IMAP"
    if ok:
        message = f"Connexion {proto_label} et SMTP réussie !"
    elif results["reception_ok"]:
        message = f"{proto_label} OK, mais SMTP échoué : {results['smtp_message']}"
    elif results["smtp_ok"]:
        message = f"SMTP OK, mais {proto_label} échoué : {results['reception_message']}"
    else:
        message = f"{proto_label} échoué : {results['reception_message']} | SMTP échoué : {results['smtp_message']}"

    return jsonify({
        "ok": ok, "message": message,
        "imap_ok": results["reception_ok"] if protocol == "imap" else None,
        "imap_message": results["reception_message"] if protocol == "imap" else None,
        "pop3_ok": results["reception_ok"] if protocol == "pop3" else None,
        "pop3_message": results["reception_message"] if protocol == "pop3" else None,
        "smtp_ok": results["smtp_ok"], "smtp_message": results["smtp_message"],
    }), 200 if ok else 500


@api_settings_bp.get("/email/presets")
def get_email_presets():
    """Retourne les présets de configuration email (Gmail, Outlook, etc.)."""
    from ....services.email import get_presets
    return jsonify(get_presets())
