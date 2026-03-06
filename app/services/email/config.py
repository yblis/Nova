import json
import os
from typing import Dict, Any
from flask import current_app


_DEFAULT_CONFIG = {
    "reception_protocol": "imap",
    "imap_host": "",
    "imap_port": 993,
    "imap_encryption": "tls",
    "pop3_host": "",
    "pop3_port": 995,
    "pop3_encryption": "tls",
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_encryption": "starttls",
    "email_address": "",
    "auth_type": "password",
    "password_encrypted": "",
    "oauth2_client_id": "",
    "oauth2_client_secret_encrypted": "",
    "oauth2_refresh_token_encrypted": "",
    "max_emails": 10,
    "default_folder": "INBOX",
    "timeout": 15,
    "auto_summarize": True,
    "include_attachments_info": True,
}

EMAIL_PRESETS = {
    "gmail": {
        "label": "Gmail",
        "imap_host": "imap.gmail.com",
        "imap_port": 993,
        "imap_encryption": "tls",
        "pop3_host": "pop.gmail.com",
        "pop3_port": 995,
        "pop3_encryption": "tls",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_encryption": "starttls",
    },
    "outlook": {
        "label": "Outlook / Office 365",
        "imap_host": "outlook.office365.com",
        "imap_port": 993,
        "imap_encryption": "tls",
        "pop3_host": "outlook.office365.com",
        "pop3_port": 995,
        "pop3_encryption": "tls",
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "smtp_encryption": "starttls",
    },
    "yahoo": {
        "label": "Yahoo Mail",
        "imap_host": "imap.mail.yahoo.com",
        "imap_port": 993,
        "imap_encryption": "tls",
        "pop3_host": "pop.mail.yahoo.com",
        "pop3_port": 995,
        "pop3_encryption": "tls",
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "smtp_encryption": "starttls",
    },
    "ovh": {
        "label": "OVH",
        "imap_host": "ssl0.ovh.net",
        "imap_port": 993,
        "imap_encryption": "tls",
        "pop3_host": "ssl0.ovh.net",
        "pop3_port": 995,
        "pop3_encryption": "tls",
        "smtp_host": "ssl0.ovh.net",
        "smtp_port": 465,
        "smtp_encryption": "tls",
    },
    "ionos": {
        "label": "IONOS / 1&1",
        "imap_host": "imap.ionos.fr",
        "imap_port": 993,
        "imap_encryption": "tls",
        "pop3_host": "pop.ionos.fr",
        "pop3_port": 995,
        "pop3_encryption": "tls",
        "smtp_host": "smtp.ionos.fr",
        "smtp_port": 465,
        "smtp_encryption": "tls",
    },
}


def _get_config_path() -> str:
    try:
        return os.path.join(current_app.root_path, "data", "email.json")
    except RuntimeError:
        return os.path.join(os.path.dirname(__file__), "..", "data", "email.json")


def _load_config() -> Dict[str, Any]:
    config_path = _get_config_path()
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                return {**_DEFAULT_CONFIG, **loaded}
    except Exception:
        pass
    return dict(_DEFAULT_CONFIG)


def _save_config(config: Dict[str, Any]) -> bool:
    config_path = _get_config_path()
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f"Failed to save email config: {e}")
        except RuntimeError:
            pass
        return False


def get_config() -> Dict[str, Any]:
    config = _load_config()
    safe = dict(config)
    safe["has_password"] = bool(safe.get("password_encrypted"))
    safe["has_oauth2_secret"] = bool(safe.get("oauth2_client_secret_encrypted"))
    safe.pop("password_encrypted", None)
    safe.pop("oauth2_client_secret_encrypted", None)
    safe.pop("oauth2_refresh_token_encrypted", None)
    return safe


def set_config(updates: Dict[str, Any]) -> bool:
    from ..crypto_service import encrypt_api_key

    config = _load_config()

    if "password" in updates and updates["password"]:
        config["password_encrypted"] = encrypt_api_key(updates["password"])
        del updates["password"]
    elif "password" in updates:
        del updates["password"]

    if "oauth2_client_secret" in updates and updates["oauth2_client_secret"]:
        config["oauth2_client_secret_encrypted"] = encrypt_api_key(updates["oauth2_client_secret"])
        del updates["oauth2_client_secret"]
    elif "oauth2_client_secret" in updates:
        del updates["oauth2_client_secret"]

    updates.pop("password_encrypted", None)
    updates.pop("oauth2_client_secret_encrypted", None)
    updates.pop("oauth2_refresh_token_encrypted", None)
    updates.pop("has_password", None)
    updates.pop("has_oauth2_secret", None)

    config.update(updates)
    return _save_config(config)


def get_presets() -> Dict[str, Any]:
    return EMAIL_PRESETS
