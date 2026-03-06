from flask import Blueprint, jsonify, request, current_app
from ....services.server_manager import ServerManager

api_settings_bp = Blueprint("api_settings", __name__)


def _get_manager() -> ServerManager:
    data_path = current_app.root_path + "/data/servers.json"
    return ServerManager(data_path)


def _validate_base_url(url: str) -> tuple[bool, str | None]:
    url = (url or "").strip()
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
    except Exception:
        return False, "URL invalide"
    if p.scheme not in {"http", "https"}:
        return False, "Schéma doit être http ou https"
    if not p.netloc:
        return False, "Hôte requis"
    return True, None


def _get_provider_manager():
    """Retourne une instance du ProviderManager."""
    from ....services.provider_manager import ProviderManager
    data_path = current_app.root_path + "/data/providers.json"
    return ProviderManager(data_path)


# Import sub-modules to register routes on the blueprint
from . import servers      # noqa: E402, F401
from . import web_search   # noqa: E402, F401
from . import email        # noqa: E402, F401
from . import llm          # noqa: E402, F401
from . import audio        # noqa: E402, F401
from . import providers    # noqa: E402, F401
from . import bookstack    # noqa: E402, F401
