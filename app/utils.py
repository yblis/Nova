from flask import current_app
from app.services.server_manager import ServerManager

def get_effective_ollama_base_url() -> str:
    # Use ServerManager
    data_path = current_app.root_path + "/data/servers.json"
    mgr = ServerManager(data_path)
    return mgr.get_active_server_url()

