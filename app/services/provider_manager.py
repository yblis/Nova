"""
Gestionnaire de fournisseurs LLM.

Gère la persistance et la récupération des configurations de fournisseurs.
Remplace ServerManager pour une gestion étendue multi-providers.
"""

import json
import os
import uuid
from typing import List, Dict, Optional, Any
from flask import current_app

from .crypto_service import encrypt_api_key, decrypt_api_key, mask_api_key


# Types de fournisseurs supportés avec leurs métadonnées
PROVIDER_TYPES = {
    "ollama": {
        "name": "Ollama",
        "requires_api_key": False,
        "requires_url": True,
        "default_url": "http://localhost:11434",
        "color": "blue",
        "icon": "server",
        "description": "Serveur Ollama local ou distant"
    },
    "lmstudio": {
        "name": "LM Studio",
        "requires_api_key": False,
        "requires_url": True,
        "default_url": "http://localhost:1234/v1",
        "color": "teal",
        "icon": "desktop",
        "description": "LM Studio en mode serveur local"
    },
    "openai": {
        "name": "OpenAI",
        "requires_api_key": True,
        "requires_url": False,
        "default_url": "https://api.openai.com/v1",
        "color": "emerald",
        "icon": "sparkles",
        "description": "API OpenAI officielle (GPT-4, GPT-4o, etc.)"
    },
    "anthropic": {
        "name": "Anthropic",
        "requires_api_key": True,
        "requires_url": False,
        "default_url": "https://api.anthropic.com",
        "color": "amber",
        "icon": "beaker",
        "description": "API Anthropic (Claude 3.5, Claude 3, etc.)"
    },
    "gemini": {
        "name": "Google Gemini",
        "requires_api_key": True,
        "requires_url": False,
        "default_url": "",
        "color": "purple",
        "icon": "cube",
        "description": "API Google Gemini (Gemini 1.5 Pro, Flash, etc.)"
    },
    "mistral": {
        "name": "Mistral AI",
        "requires_api_key": True,
        "requires_url": False,
        "default_url": "https://api.mistral.ai/v1",
        "color": "orange",
        "icon": "bolt",
        "description": "API Mistral AI officielle"
    },
    "groq": {
        "name": "Groq",
        "requires_api_key": True,
        "requires_url": False,
        "default_url": "https://api.groq.com/openai/v1",
        "color": "cyan",
        "icon": "lightning-bolt",
        "description": "API Groq ultra-rapide"
    },
    "openrouter": {
        "name": "OpenRouter",
        "requires_api_key": True,
        "requires_url": False,
        "default_url": "https://openrouter.ai/api/v1",
        "color": "pink",
        "icon": "globe",
        "description": "Agrégateur multi-modèles (Claude, GPT, Llama, etc.)",
        "extra_headers": ["HTTP-Referer", "X-Title"]
    },
    "deepseek": {
        "name": "DeepSeek",
        "requires_api_key": True,
        "requires_url": False,
        "default_url": "https://api.deepseek.com",
        "color": "indigo",
        "icon": "code",
        "description": "API DeepSeek (DeepSeek-V3, Coder, etc.)"
    },
    "qwen": {
        "name": "Qwen (Alibaba)",
        "requires_api_key": True,
        "requires_url": False,
        "default_url": "",
        "color": "rose",
        "icon": "cloud",
        "description": "API DashScope (Qwen-Max, Qwen-Plus, etc.)"
    },
    "openai_compatible": {
        "name": "OpenAI Compatible",
        "requires_api_key": False,
        "requires_url": True,
        "default_url": "http://localhost:8080/v1",
        "color": "slate",
        "icon": "plug",
        "description": "API compatible OpenAI générique (vLLM, text-generation-inference, etc.)"
    }
}


class ProviderManager:
    """Gestionnaire de fournisseurs LLM avec persistance JSON."""
    
    def __init__(self, data_path: str):
        """
        Initialise le gestionnaire.
        
        Args:
            data_path: Chemin vers le fichier providers.json
        """
        self.data_path = data_path
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """Crée le fichier de données s'il n'existe pas, avec un provider Ollama par défaut."""
        if not os.path.exists(self.data_path):
            import time
            
            # Create a default Ollama provider
            default_provider_id = str(uuid.uuid4())
            timestamp = int(time.time())
            
            default_data = {
                "active_provider_id": default_provider_id,
                "providers": [
                    {
                        "id": default_provider_id,
                        "name": "Ollama (localhost)",
                        "type": "ollama",
                        "url": "http://localhost:11434",
                        "api_key_encrypted": "",
                        "extra_headers": {},
                        "default_model": "",
                        "created_at": timestamp,
                        "updated_at": timestamp
                    }
                ]
            }
            self._save_data(default_data)
            print("Created default Ollama provider (http://localhost:11434)")
    
    def _load_data(self) -> Dict:
        """Charge les données depuis le fichier JSON."""
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"active_provider_id": None, "providers": []}
    
    def _save_data(self, data: Dict):
        """Sauvegarde les données dans le fichier JSON."""
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_providers(self, include_api_key_masked: bool = True) -> List[Dict]:
        """
        Récupère la liste des fournisseurs.
        
        Args:
            include_api_key_masked: Si True, inclut une version masquée de la clé API
            
        Returns:
            Liste des fournisseurs (sans les clés API en clair)
        """
        data = self._load_data()
        providers = data.get("providers", [])
        
        result = []
        for p in providers:
            provider = {
                "id": p["id"],
                "name": p["name"],
                "type": p["type"],
                "url": p.get("url", ""),
                "extra_headers": p.get("extra_headers", {}),
                "has_api_key": bool(p.get("api_key_encrypted")),
                "default_model": p.get("default_model", ""),
                "created_at": p.get("created_at"),
                "updated_at": p.get("updated_at")
            }
            
            if include_api_key_masked and p.get("api_key_encrypted"):
                decrypted = decrypt_api_key(p["api_key_encrypted"])
                provider["api_key_masked"] = mask_api_key(decrypted) if decrypted else "•••••"
            
            result.append(provider)
        
        return result
    
    def get_provider(self, provider_id: str, include_api_key: bool = False) -> Optional[Dict]:
        """
        Récupère un fournisseur par son ID.
        
        Args:
            provider_id: ID du fournisseur
            include_api_key: Si True, inclut la clé API déchiffrée
            
        Returns:
            Le fournisseur ou None
        """
        data = self._load_data()
        for p in data.get("providers", []):
            if p["id"] == provider_id:
                result = {
                    "id": p["id"],
                    "name": p["name"],
                    "type": p["type"],
                    "url": p.get("url", ""),
                    "extra_headers": p.get("extra_headers", {}),
                    "has_api_key": bool(p.get("api_key_encrypted")),
                    "default_model": p.get("default_model", "")
                }
                
                if include_api_key and p.get("api_key_encrypted"):
                    result["api_key"] = decrypt_api_key(p["api_key_encrypted"])
                
                return result
        return None
    
    def add_provider(
        self,
        name: str,
        provider_type: str,
        url: str = "",
        api_key: str = "",
        extra_headers: Dict[str, str] = None
    ) -> Dict:
        """
        Ajoute un nouveau fournisseur.
        
        Args:
            name: Nom d'affichage
            provider_type: Type de fournisseur (ollama, openai, etc.)
            url: URL du serveur (optionnel selon le type)
            api_key: Clé API en clair (sera chiffrée)
            extra_headers: Headers supplémentaires (pour OpenRouter)
        
        Returns:
            Le fournisseur créé (sans la clé API)
        """
        import time
        
        if provider_type not in PROVIDER_TYPES:
            raise ValueError(f"Type de fournisseur invalide: {provider_type}")
        
        data = self._load_data()
        
        # Utiliser l'URL par défaut si non fournie
        if not url:
            url = PROVIDER_TYPES[provider_type].get("default_url", "")
        
        new_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        new_provider = {
            "id": new_id,
            "name": name,
            "type": provider_type,
            "url": url,
            "api_key_encrypted": encrypt_api_key(api_key) if api_key else "",
            "extra_headers": extra_headers or {},
            "default_model": "",
            "created_at": timestamp,
            "updated_at": timestamp
        }
        
        data["providers"].append(new_provider)
        
        # Si c'est le premier provider, le définir comme actif
        if not data.get("active_provider_id"):
            data["active_provider_id"] = new_id
        
        self._save_data(data)
        
        return {
            "id": new_id,
            "name": name,
            "type": provider_type,
            "url": url,
            "has_api_key": bool(api_key),
            "extra_headers": extra_headers or {}
        }
    
    def update_provider(
        self,
        provider_id: str,
        name: str = None,
        url: str = None,
        api_key: str = None,
        extra_headers: Dict[str, str] = None
    ) -> Optional[Dict]:
        """
        Met à jour un fournisseur existant.
        
        Args:
            provider_id: ID du fournisseur
            name: Nouveau nom (optionnel)
            url: Nouvelle URL (optionnel)
            api_key: Nouvelle clé API (optionnel, vide pour ne pas changer)
            extra_headers: Nouveaux headers (optionnel)
        
        Returns:
            Le fournisseur mis à jour ou None si non trouvé
        """
        import time
        
        data = self._load_data()
        
        for p in data["providers"]:
            if p["id"] == provider_id:
                if name is not None:
                    p["name"] = name
                if url is not None:
                    p["url"] = url
                if api_key is not None and api_key != "":
                    p["api_key_encrypted"] = encrypt_api_key(api_key)
                if extra_headers is not None:
                    p["extra_headers"] = extra_headers
                
                p["updated_at"] = int(time.time())
                
                self._save_data(data)
                
                return {
                    "id": p["id"],
                    "name": p["name"],
                    "type": p["type"],
                    "url": p.get("url", ""),
                    "has_api_key": bool(p.get("api_key_encrypted")),
                    "extra_headers": p.get("extra_headers", {})
                }
        
        return None
    
    def delete_provider(self, provider_id: str) -> bool:
        """
        Supprime un fournisseur.
        
        Args:
            provider_id: ID du fournisseur à supprimer
            
        Returns:
            True si supprimé, False si non trouvé
        """
        data = self._load_data()
        original_len = len(data["providers"])
        
        data["providers"] = [p for p in data["providers"] if p["id"] != provider_id]
        
        if len(data["providers"]) == original_len:
            return False
        
        # Si le provider actif a été supprimé, en choisir un autre
        if data.get("active_provider_id") == provider_id:
            data["active_provider_id"] = data["providers"][0]["id"] if data["providers"] else None
        
        self._save_data(data)
        return True
    
    def set_active_provider(self, provider_id: str) -> bool:
        """
        Définit le fournisseur actif.
        
        Args:
            provider_id: ID du fournisseur à activer
            
        Returns:
            True si réussi, False si fournisseur non trouvé
        """
        data = self._load_data()
        
        if not any(p["id"] == provider_id for p in data["providers"]):
            return False
        
        data["active_provider_id"] = provider_id
        self._save_data(data)
        return True
    
    def get_active_provider(self, include_api_key: bool = False) -> Optional[Dict]:
        """
        Récupère le fournisseur actif.
        
        Args:
            include_api_key: Si True, inclut la clé API déchiffrée
            
        Returns:
            Le fournisseur actif ou None
        """
        data = self._load_data()
        active_id = data.get("active_provider_id")
        
        if not active_id:
            # Fallback au premier si aucun actif défini
            if data["providers"]:
                return self.get_provider(data["providers"][0]["id"], include_api_key)
            return None
        
        return self.get_provider(active_id, include_api_key)
    
    def get_active_provider_id(self) -> Optional[str]:
        """Retourne l'ID du fournisseur actif."""
        data = self._load_data()
        return data.get("active_provider_id")
    
    def set_default_model(self, provider_id: str, model_name: str) -> bool:
        """
        Définit le modèle par défaut pour un fournisseur.
        
        Args:
            provider_id: ID du fournisseur
            model_name: Nom du modèle à définir par défaut
            
        Returns:
            True si réussi, False si fournisseur non trouvé
        """
        import time
        
        data = self._load_data()
        
        for p in data["providers"]:
            if p["id"] == provider_id:
                p["default_model"] = model_name
                p["updated_at"] = int(time.time())
                self._save_data(data)
                return True
        
        return False
    
    def get_default_model(self, provider_id: str) -> Optional[str]:
        """Retourne le modèle par défaut d'un fournisseur."""
        data = self._load_data()
        for p in data.get("providers", []):
            if p["id"] == provider_id:
                return p.get("default_model", "")
        return None
    
    def is_provider_configured(self, provider_type: str) -> bool:
        """
        Vérifie si au moins un provider d'un type donné est configuré.
        
        Args:
            provider_type: Type de provider (gemini, openai, anthropic, ollama, etc.)
            
        Returns:
            True si au moins un provider de ce type est configuré et utilisable
        """
        data = self._load_data()
        
        for p in data.get("providers", []):
            if p["type"] == provider_type:
                # Pour les types qui nécessitent une API key, vérifier qu'elle existe
                type_info = PROVIDER_TYPES.get(provider_type, {})
                if type_info.get("requires_api_key"):
                    if p.get("api_key_encrypted"):
                        return True
                else:
                    # Pour les types sans API key (ollama, lmstudio), juste vérifier que l'URL est définie
                    if p.get("url"):
                        return True
        
        return False
    
    def get_provider_by_type(self, provider_type: str, include_api_key: bool = False) -> Optional[Dict]:
        """
        Récupère le premier provider configuré d'un type donné.
        
        Args:
            provider_type: Type de provider
            include_api_key: Si True, inclut la clé API déchiffrée
            
        Returns:
            Le provider ou None
        """
        data = self._load_data()
        
        for p in data.get("providers", []):
            if p["type"] == provider_type:
                type_info = PROVIDER_TYPES.get(provider_type, {})
                
                # Vérifier que le provider est utilisable
                if type_info.get("requires_api_key"):
                    if not p.get("api_key_encrypted"):
                        continue
                elif not p.get("url"):
                    continue
                
                return self.get_provider(p["id"], include_api_key)
        
        return None


def get_provider_manager() -> ProviderManager:
    """Factory pour obtenir une instance du ProviderManager."""
    try:
        data_path = os.path.join(current_app.root_path, "data", "providers.json")
    except RuntimeError:
        # Hors contexte Flask
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "providers.json")
    
    return ProviderManager(data_path)

def ensure_local_audio_providers():
    """Vérifie et ajoute les providers audio locaux si manquants."""
    mgr = get_provider_manager()
    providers = mgr.get_providers(include_api_key_masked=False)
    
    # Check Whisper
    whisper_url = "http://nova-whisper:8000/v1"
    has_whisper = any(p["url"] == whisper_url for p in providers if p["type"] == "openai_compatible")
    if not has_whisper:
        try:
            mgr.add_provider(
                name="Local Whisper (STT)",
                provider_type="openai_compatible",
                url=whisper_url,
                api_key="sk-dummy" # API key often required by clients even if ignored
            )
            print("Added Local Whisper provider")
        except Exception as e:
            print(f"Failed to add Whisper provider: {e}")

    # Check AllTalk
    alltalk_url = "http://nova-alltalk:7851/v1"
    has_alltalk = any(p["url"] == alltalk_url for p in providers if p["type"] == "openai_compatible")
    if not has_alltalk:
        try:
            mgr.add_provider(
                name="Local AllTalk (TTS)",
                provider_type="openai_compatible",
                url=alltalk_url,
                api_key="sk-dummy"
            )
            print("Added Local AllTalk provider")
        except Exception as e:
            print(f"Failed to add AllTalk provider: {e}")



def get_provider_types() -> Dict[str, Dict]:
    """Retourne les types de fournisseurs avec leurs métadonnées."""
    return PROVIDER_TYPES


def migrate_from_servers():
    """
    Migre les données de servers.json vers providers.json.
    
    Convertit les anciens serveurs Ollama en providers de type 'ollama'.
    """
    try:
        data_path = os.path.join(current_app.root_path, "data")
    except RuntimeError:
        data_path = os.path.join(os.path.dirname(__file__), "..", "data")
    
    servers_path = os.path.join(data_path, "servers.json")
    providers_path = os.path.join(data_path, "providers.json")
    
    # Ne pas migrer si providers.json existe déjà et contient des données
    if os.path.exists(providers_path):
        try:
            with open(providers_path, 'r', encoding='utf-8') as f:
                providers_data = json.load(f)
                if providers_data.get("providers"):
                    return False  # Déjà migré
        except (json.JSONDecodeError, KeyError):
            pass
    
    # Charger les anciens serveurs
    if not os.path.exists(servers_path):
        return False
    
    try:
        with open(servers_path, 'r', encoding='utf-8') as f:
            servers_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return False
    
    # Créer la structure providers
    import time
    timestamp = int(time.time())
    
    providers = []
    active_id = None
    
    for server in servers_data.get("servers", []):
        provider = {
            "id": server["id"],
            "name": server["name"],
            "type": "ollama",
            "url": server["url"],
            "api_key_encrypted": "",
            "extra_headers": {},
            "created_at": timestamp,
            "updated_at": timestamp
        }
        providers.append(provider)
        
        # Conserver le serveur actif
        if server["id"] == servers_data.get("active_server_id"):
            active_id = server["id"]
    
    # Si pas d'actif défini, prendre le premier
    if not active_id and providers:
        active_id = providers[0]["id"]
    
    new_data = {
        "active_provider_id": active_id,
        "providers": providers
    }
    
    # Sauvegarder
    os.makedirs(data_path, exist_ok=True)
    with open(providers_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)
    
    return True
