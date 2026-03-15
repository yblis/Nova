"""
Client pour les API compatibles OpenAI.

Supporte: OpenAI, LM Studio, Groq, Mistral, OpenRouter, DeepSeek.
Utilise le SDK OpenAI officiel avec base_url configurable.
"""

from typing import List, Dict, Any, Optional, Tuple, Iterable

from .base_client import BaseLLMClient
from ..llm_error_handler import LLMError, LLMErrorType, classify_openai_error


# Configuration par défaut pour chaque provider compatible OpenAI
PROVIDER_CONFIGS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "supports_vision": True
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "default_model": None,  # Dépend du modèle chargé
        "supports_vision": True,
        "default_api_key": "lm-studio",  # LM Studio n'a pas besoin de vraie clé
        "requires_v1_suffix": True,  # LM Studio nécessite /v1 dans l'URL
        "supports_model_management": True,  # Support load/unload/download via API v1
        "api_version": "v1"  # Utilise l'API v1 en priorité (fallback v0)
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "supports_vision": False
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "supports_vision": False
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-3.5-sonnet",
        "supports_vision": True,
        "extra_headers_required": ["HTTP-Referer", "X-Title"]
    },
    "openrouter_free": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3.2-3b-instruct:free",
        "supports_vision": True,
        "extra_headers_required": ["HTTP-Referer", "X-Title"],
        "free_models_only": True
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "supports_vision": False
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "default_model": "llama-3.3-70b",
        "supports_vision": False,
        "unsupported_params": ["frequency_penalty", "presence_penalty", "top_p"]
    },
    "huggingface": {
        "base_url": "https://router.huggingface.co/v1",
        "default_model": "mistralai/Mistral-7B-Instruct-v0.3",
        "supports_vision": False,
        "unsupported_params": ["frequency_penalty", "presence_penalty"]
    },
    "swama": {
        "base_url": "http://localhost:28100",
        "default_model": None,
        "supports_vision": True,
        "default_api_key": "not-needed",
        "requires_v1_suffix": True
    },
    "openai_compatible": {
        "base_url": "",
        "default_model": None,
        "supports_vision": True,
        "default_api_key": "not-needed",
        "requires_v1_suffix": True
    }
}


class OpenAICompatibleClient(BaseLLMClient):
    """Client pour les API compatibles avec le format OpenAI."""
    
    def __init__(
        self,
        provider_type: str,
        api_key: str = "",
        base_url: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le client.
        
        Args:
            provider_type: Type de provider (openai, groq, mistral, etc.)
            api_key: Clé API
            base_url: URL de base (optionnel, utilise la valeur par défaut du provider)
            extra_headers: Headers supplémentaires (pour OpenRouter)
        """
        self._provider_type = provider_type
        self._config = PROVIDER_CONFIGS.get(provider_type, {})
        
        # Utiliser l'URL fournie ou la valeur par défaut
        self._base_url = base_url or self._config.get("base_url", "")
        
        # Normaliser l'URL pour les providers qui nécessitent /v1
        if self._base_url and self._config.get("requires_v1_suffix"):
            self._base_url = self._normalize_url_with_v1(self._base_url)
        
        # Utiliser la clé API fournie ou une valeur par défaut (pour LM Studio)
        self._api_key = api_key or self._config.get("default_api_key", "")
        
        # Headers supplémentaires
        self._extra_headers = extra_headers or {}
        
        # Client OpenAI lazy-loaded
        self._client = None
    
    def _normalize_url_with_v1(self, url: str) -> str:
        """
        Normalise l'URL pour s'assurer qu'elle inclut /v1.
        
        Les API compatibles OpenAI (comme LM Studio) utilisent /v1 dans leur chemin.
        Cette méthode s'assure que l'URL est correctement formatée.
        
        Args:
            url: L'URL de base fournie
            
        Returns:
            L'URL normalisée avec /v1
        """
        if not url:
            return url
        
        # Retirer le slash final s'il existe
        url = url.rstrip('/')
        
        # Si l'URL se termine déjà par /v1, ne rien faire
        if url.endswith('/v1'):
            return url
        
        # Sinon, ajouter /v1
        return f"{url}/v1"
    
    def _get_client(self):
        """Retourne le client OpenAI (lazy loading)."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise LLMError(
                    "SDK OpenAI non installé. Exécutez: pip install openai",
                    self._provider_type,
                    LLMErrorType.UNKNOWN
                )
            
            # Construire les headers
            default_headers = {}
            
            # Headers spécifiques à OpenRouter
            if self._provider_type == "openrouter":
                default_headers["HTTP-Referer"] = self._extra_headers.get("HTTP-Referer", "https://nova.local")
                default_headers["X-Title"] = self._extra_headers.get("X-Title", "Nova")
            
            # Ajouter les headers personnalisés
            default_headers.update(self._extra_headers)
            
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                default_headers=default_headers if default_headers else None
            )
        
        return self._client
    
    @property
    def provider_name(self) -> str:
        return self._provider_type
    
    def list_models(self) -> List[Dict[str, Any]]:
        """Liste les modèles disponibles via l'API."""
        # Pour LM Studio, utiliser l'API native qui donne plus d'infos
        if self._provider_type == "lmstudio":
            return self._list_models_lmstudio_native()
        
        # Pour Hugging Face, utiliser l'API du Hub
        if self._provider_type == "huggingface":
            return self._list_models_huggingface_hub()
        
        try:
            client = self._get_client()
            response = client.models.list()
            
            models = []
            for model in response.data:
                model_id = model.id
                
                # Filter for free models only if configured (OpenRouter Free)
                if self._config.get("free_models_only"):
                    if not model_id.endswith(":free"):
                        continue
                
                models.append({
                    "id": model_id,
                    "name": model_id,
                    "description": getattr(model, "description", "") or "",
                    "created": getattr(model, "created", None),
                    "owned_by": getattr(model, "owned_by", "")
                })
            
            # Trier par nom
            models.sort(key=lambda x: x["name"])
            
            return models
            
        except Exception as e:
            # Fallback pour les providers qui ne supportent pas /v1/models (ex: AllTalk)
            if "404" in str(e) or "Not Found" in str(e):
                import logging
                logging.getLogger(__name__).warning(f"Could not list models for {self._provider_type}: {e}. Using fallback.")
                
                # S'il y a un modèle par défaut configuré, on l'utilise
                default_model = self.get_default_model()
                if default_model:
                     return [{"id": default_model, "name": default_model, "owned_by": "system"}]
                
                # Sinon on retourne des modèles génériques pour l'audio si c'est de l'audio
                # (On ne sait pas ici si c'est audio, mais 'tts-1' est un standard openAI)
                return [
                    {"id": "tts-1", "name": "tts-1 (Default)", "owned_by": "system"},
                    {"id": "whisper-1", "name": "whisper-1", "owned_by": "system"}
                ]

            raise classify_openai_error(e, self._provider_type)

    def _list_models_huggingface_hub(self) -> List[Dict[str, Any]]:
        """Liste les modèles Hugging Face disponibles pour l'inférence via l'API du Hub."""
        try:
            import httpx
            
            url = "https://huggingface.co/api/models"
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            
            # Filtrer pour ne garder que les modèles:
            # - disponibles pour l'inférence (inference=warm)
            # - de type text-generation (chat/completion)
            # - compatibles avec text-generation-inference
            params = {
                "limit": 100,
                "sort": "likes",
                "direction": "-1",
                "pipeline_tag": "text-generation",
                "inference": "warm",  # Seulement les modèles disponibles pour l'inférence
                "other": "text-generation-inference"  # Compatible TGI
            }
            
            with httpx.Client(timeout=10.0) as http_client:
                response = http_client.get(url, headers=headers, params=params)
                response.raise_for_status()
                models_list = response.json()
            
            models = []
            for model in models_list:
                model_id = model.get("modelId", "")
                likes = model.get("likes", 0)
                downloads = model.get("downloads", 0)
                
                models.append({
                    "id": model_id,
                    "name": model_id,
                    "description": f"❤️ {likes:,} | ⬇️ {downloads:,}",
                    "created": None,
                    "owned_by": "Hugging Face Hub"
                })
            
            return models
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to list Hugging Face models via Hub API: {e}")
            # Fallback sur le modèle par défaut si l'API Hub échoue
            default = self.get_default_model()
            return [{"id": default, "name": default, "owned_by": "system"}] if default else []
    
    def _list_models_lmstudio_native(self) -> List[Dict[str, Any]]:
        """Liste tous les modèles LM Studio via l'API native.
        
        Essaie d'abord l'API v1 (LM Studio 0.4.0+), puis fallback sur v0.
        """
        try:
            import httpx
            
            # Construire l'URL de base sans /v1 pour l'API native LM Studio
            base_url = self._base_url
            if base_url.endswith('/v1'):
                base_url = base_url[:-3]
            
            with httpx.Client(timeout=5.0) as http_client:
                # Essayer d'abord l'API v1 (LM Studio 0.4.0+)
                url_v1 = f"{base_url}/api/v1/models"
                response = http_client.get(url_v1)
                
                # Si v1 échoue avec 404, fallback sur v0
                if response.status_code == 404:
                    return self._list_models_lmstudio_v0(base_url, http_client)
                
                response.raise_for_status()
                response_data = response.json()
            
            # API v1 retourne {"models": [...]}
            models_list = response_data.get("models", [])
            
            models = []
            for model in models_list:
                if isinstance(model, dict):
                    # Déterminer si le modèle est chargé via loaded_instances
                    loaded_instances = model.get("loaded_instances", [])
                    is_loaded = len(loaded_instances) > 0
                    
                    # Extraire les infos de quantization (format v1: objet)
                    quant_info = model.get("quantization", {})
                    quant_name = quant_info.get("name", "") if isinstance(quant_info, dict) else str(quant_info)
                    quant_bits = quant_info.get("bits_per_weight") if isinstance(quant_info, dict) else None
                    
                    # Extraire capabilities
                    capabilities = model.get("capabilities", {})
                    
                    models.append({
                        # Compatibilité: "id" utilise "key" de v1
                        "id": model.get("key", ""),
                        "name": model.get("display_name") or model.get("key", "Unknown"),
                        "key": model.get("key", ""),
                        "display_name": model.get("display_name", ""),
                        "quantization": quant_name,
                        "quantization_bits": quant_bits,
                        "arch": model.get("architecture", ""),
                        "type": model.get("type", "llm"),
                        "state": "loaded" if is_loaded else "not-loaded",
                        "loaded_instances": loaded_instances,
                        "max_context_length": model.get("max_context_length", 0),
                        "publisher": model.get("publisher", ""),
                        "format": model.get("format", ""),
                        "size_bytes": model.get("size_bytes", 0),
                        "params_string": model.get("params_string", ""),
                        "capabilities": capabilities,
                        "supports_vision": capabilities.get("vision", False) if isinstance(capabilities, dict) else False,
                        "supports_tools": capabilities.get("trained_for_tool_use", False) if isinstance(capabilities, dict) else False,
                        "description": model.get("description", ""),
                        "api_version": "v1"
                    })
            
            # Trier par nom
            models.sort(key=lambda x: x["name"])
            
            return models
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to list LM Studio models via v1 API: {e}")
            # Fallback to OpenAI compatible API
            try:
                client = self._get_client()
                response = client.models.list()
                return [{"id": m.id, "name": m.id, "api_version": "openai"} for m in response.data]
            except Exception:
                return []
    
    def _list_models_lmstudio_v0(self, base_url: str, http_client) -> List[Dict[str, Any]]:
        """Fallback sur l'API v0 pour les anciennes versions de LM Studio (<0.4.0).
        
        Args:
            base_url: URL de base sans /v1
            http_client: Client HTTP actif
            
        Returns:
            Liste des modèles au format normalisé
        """
        url = f"{base_url}/api/v0/models"
        response = http_client.get(url)
        response.raise_for_status()
        response_data = response.json()
        
        # API v0 retourne {"object": "list", "data": [...]}
        models_list = response_data.get("data", []) if isinstance(response_data, dict) else response_data
        
        models = []
        for model in models_list:
            if isinstance(model, dict):
                models.append({
                    "id": model.get("id", ""),
                    "name": model.get("id", "Unknown"),
                    "key": model.get("id", ""),
                    "display_name": model.get("id", ""),
                    "quantization": model.get("quantization", ""),
                    "arch": model.get("arch", ""),
                    "type": model.get("type", "llm"),
                    "state": model.get("state", "not-loaded"),
                    "max_context_length": model.get("max_context_length", 0),
                    "publisher": model.get("publisher", ""),
                    "compatibility_type": model.get("compatibility_type", ""),
                    "api_version": "v0"
                })
        
        models.sort(key=lambda x: x["name"])
        return models
    
    def list_loaded_models(self) -> List[Dict[str, Any]]:
        """
        Liste les modèles actuellement chargés en mémoire.
        
        Pour LM Studio v1, utilise le champ loaded_instances de /api/v1/models.
        Pour v0, filtre par state="loaded".
        
        Returns:
            Liste des modèles chargés avec leurs informations
        """
        if self._provider_type != "lmstudio":
            return []
        
        try:
            # Récupérer tous les modèles avec leur état
            all_models = self._list_models_lmstudio_native()
            
            loaded_models = []
            for model in all_models:
                # v1: vérifier loaded_instances, v0: vérifier state
                if model.get("api_version") == "v1":
                    loaded_instances = model.get("loaded_instances", [])
                    for instance in loaded_instances:
                        loaded_models.append({
                            "name": model.get("display_name") or model.get("key", "Unknown"),
                            "id": model.get("key", ""),
                            "instance_id": instance.get("id", ""),
                            "size": model.get("size_bytes", 0),
                            "context_length": instance.get("config", {}).get("context_length", 0),
                            "max_context_length": model.get("max_context_length", 0),
                            "quantization": model.get("quantization", ""),
                            "arch": model.get("arch", ""),
                            "type": model.get("type", "llm"),
                            "format": model.get("format", ""),
                            "flash_attention": instance.get("config", {}).get("flash_attention", False),
                            "capabilities": model.get("capabilities", {}),
                            "provider": "lmstudio",
                            "api_version": "v1"
                        })
                elif model.get("state") == "loaded":
                    # Fallback v0
                    loaded_models.append({
                        "name": model.get("name", "Unknown"),
                        "id": model.get("id", ""),
                        "instance_id": model.get("id", ""),
                        "size": 0,
                        "context_length": model.get("max_context_length", 0),
                        "quantization": model.get("quantization", ""),
                        "arch": model.get("arch", ""),
                        "type": model.get("type", "llm"),
                        "provider": "lmstudio",
                        "api_version": "v0"
                    })
            
            return loaded_models
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to list loaded LM Studio models: {e}")
            return []
    
    def load_model_lmstudio(
        self,
        model_key: str,
        context_length: Optional[int] = None,
        flash_attention: Optional[bool] = None,
        eval_batch_size: Optional[int] = None,
        num_experts: Optional[int] = None,
        offload_kv_cache_to_gpu: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Charge un modèle dans LM Studio via l'API v1.
        
        Requiert LM Studio 0.4.0+.
        
        Args:
            model_key: Identifiant du modèle (champ "key" de l'API v1)
            context_length: Longueur de contexte (optionnel)
            flash_attention: Activer Flash Attention (optionnel)
            eval_batch_size: Taille du batch d'évaluation (optionnel)
            num_experts: Nombre d'experts MoE (optionnel)
            offload_kv_cache_to_gpu: Décharger le cache KV sur GPU (optionnel)
            
        Returns:
            Informations sur le modèle chargé:
            - type: "llm" | "embedding"
            - instance_id: Identifiant de l'instance
            - load_time_seconds: Temps de chargement
            - status: "loaded"
            - load_config: Configuration appliquée
            
        Raises:
            LLMError: Si le chargement échoue
        """
        if self._provider_type != "lmstudio":
            raise LLMError(
                "Cette méthode n'est disponible que pour LM Studio",
                self._provider_type,
                LLMErrorType.UNKNOWN
            )
        
        try:
            import httpx
            
            base_url = self._base_url.rstrip('/v1') if self._base_url.endswith('/v1') else self._base_url
            url = f"{base_url}/api/v1/models/load"
            
            # Construire le payload
            payload = {"model": model_key, "echo_load_config": True}
            
            if context_length is not None:
                payload["context_length"] = context_length
            if flash_attention is not None:
                payload["flash_attention"] = flash_attention
            if eval_batch_size is not None:
                payload["eval_batch_size"] = eval_batch_size
            if num_experts is not None:
                payload["num_experts"] = num_experts
            if offload_kv_cache_to_gpu is not None:
                payload["offload_kv_cache_to_gpu"] = offload_kv_cache_to_gpu
            
            # Timeout plus long pour le chargement de gros modèles
            with httpx.Client(timeout=120.0) as http_client:
                response = http_client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            import httpx
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                raise LLMError(
                    "L'API v1 n'est pas disponible. Mettez à jour LM Studio vers 0.4.0+",
                    self._provider_type,
                    LLMErrorType.SERVER_ERROR
                )
            raise LLMError(
                f"Erreur lors du chargement du modèle: {e}",
                self._provider_type,
                LLMErrorType.SERVER_ERROR
            )
    
    def unload_model_lmstudio(self, instance_id: str) -> Dict[str, Any]:
        """Décharge un modèle de LM Studio via l'API v1.
        
        Requiert LM Studio 0.4.0+.
        
        Args:
            instance_id: Identifiant de l'instance à décharger
                         (retourné par load ou dans loaded_instances)
            
        Returns:
            {"instance_id": "..."} si succès
            
        Raises:
            LLMError: Si le déchargement échoue
        """
        if self._provider_type != "lmstudio":
            raise LLMError(
                "Cette méthode n'est disponible que pour LM Studio",
                self._provider_type,
                LLMErrorType.UNKNOWN
            )
        
        try:
            import httpx
            
            base_url = self._base_url.rstrip('/v1') if self._base_url.endswith('/v1') else self._base_url
            url = f"{base_url}/api/v1/models/unload"
            
            # ⚠️ v1 utilise "instance_id" et non "model"
            payload = {"instance_id": instance_id}
            
            with httpx.Client(timeout=30.0) as http_client:
                response = http_client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            import httpx
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                raise LLMError(
                    "L'API v1 n'est pas disponible. Mettez à jour LM Studio vers 0.4.0+",
                    self._provider_type,
                    LLMErrorType.SERVER_ERROR
                )
            raise LLMError(
                f"Erreur lors du déchargement du modèle: {e}",
                self._provider_type,
                LLMErrorType.SERVER_ERROR
            )
    
    def download_model_lmstudio(
        self,
        model: str,
        quantization: Optional[str] = None
    ) -> Dict[str, Any]:
        """Télécharge un modèle via l'API v1 de LM Studio.
        
        Requiert LM Studio 0.4.0+.
        
        Args:
            model: Identifiant du modèle (ex: "ibm/granite-4-micro")
                   ou lien Hugging Face
            quantization: Niveau de quantization (ex: "Q4_K_M")
                          Seulement pour les liens Hugging Face
            
        Returns:
            {
                "job_id": "job_xxx",  # Absent si already_downloaded
                "status": "downloading" | "already_downloaded",
                "total_size_bytes": 12345,
                "started_at": "2025-..."
            }
            
        Raises:
            LLMError: Si le téléchargement échoue
        """
        if self._provider_type != "lmstudio":
            raise LLMError(
                "Cette méthode n'est disponible que pour LM Studio",
                self._provider_type,
                LLMErrorType.UNKNOWN
            )
        
        try:
            import httpx
            
            base_url = self._base_url.rstrip('/v1') if self._base_url.endswith('/v1') else self._base_url
            url = f"{base_url}/api/v1/models/download"
            
            payload = {"model": model}
            if quantization:
                payload["quantization"] = quantization
            
            with httpx.Client(timeout=30.0) as http_client:
                response = http_client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            import httpx
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                raise LLMError(
                    "L'API v1 n'est pas disponible. Mettez à jour LM Studio vers 0.4.0+",
                    self._provider_type,
                    LLMErrorType.SERVER_ERROR
                )
            raise LLMError(
                f"Erreur lors du téléchargement du modèle: {e}",
                self._provider_type,
                LLMErrorType.SERVER_ERROR
            )
    
    def get_download_status_lmstudio(self, job_id: str) -> Dict[str, Any]:
        """Récupère l'état d'un téléchargement en cours.
        
        Args:
            job_id: Identifiant du job retourné par download_model_lmstudio
            
        Returns:
            {
                "job_id": "job_xxx",
                "status": "downloading" | "paused" | "completed" | "failed",
                "bytes_per_second": 12345,
                "estimated_completion": "2025-...",
                "total_size_bytes": 12345,
                "downloaded_bytes": 1234,
                "started_at": "2025-...",
                "completed_at": "2025-..."  # Si completed
            }
        """
        if self._provider_type != "lmstudio":
            raise LLMError(
                "Cette méthode n'est disponible que pour LM Studio",
                self._provider_type,
                LLMErrorType.UNKNOWN
            )
        
        try:
            import httpx
            
            base_url = self._base_url.rstrip('/v1') if self._base_url.endswith('/v1') else self._base_url
            url = f"{base_url}/api/v1/models/download/status/{job_id}"
            
            with httpx.Client(timeout=10.0) as http_client:
                response = http_client.get(url)
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            raise LLMError(
                f"Erreur lors de la récupération du statut: {e}",
                self._provider_type,
                LLMErrorType.UNKNOWN
            )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        images: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Envoie une requête de chat non-streaming."""
        try:
            client = self._get_client()
            normalized_opts = self.normalize_options(options)
            
            # Préparer les messages avec images si nécessaire
            prepared_messages = self._prepare_messages_with_images(messages, images)
            
            response = client.chat.completions.create(
                model=model,
                messages=prepared_messages,
                stream=False,
                **normalized_opts
            )
            
            choice = response.choices[0] if response.choices else None
            
            return {
                "message": {
                    "role": "assistant",
                    "content": choice.message.content if choice else ""
                },
                "done": True,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            }
            
        except Exception as e:
            raise classify_openai_error(e, self._provider_type)
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        images: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Iterable[Dict[str, Any]]:
        """Envoie une requête de chat streaming.
        
        Supporte l'extraction du contenu 'thinking' pour les modèles de raisonnement :
        - Via le champ `reasoning_content` dans delta (DeepSeek, Hugging Face)
        - Via les balises <think>...</think> dans le contenu (Qwen3)
        """
        try:
            client = self._get_client()
            normalized_opts = self.normalize_options(options)
            
            # Préparer les messages avec images si nécessaire
            prepared_messages = self._prepare_messages_with_images(messages, images)
            
            stream = client.chat.completions.create(
                model=model,
                messages=prepared_messages,
                stream=True,
                **normalized_opts
            )
            
            # État pour parser les balises <think>...</think>
            in_thinking = False
            buffer = ""
            
            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    raw_content = delta.content or ""
                    
                    # Vérifier si le delta contient reasoning_content (DeepSeek/HF format)
                    reasoning_content = getattr(delta, 'reasoning_content', None) or ""
                    
                    # Si on a du reasoning_content directement, l'utiliser
                    if reasoning_content:
                        yield {
                            "message": {
                                "role": "assistant",
                                "content": raw_content,
                                "thinking": reasoning_content
                            },
                            "done": chunk.choices[0].finish_reason is not None
                        }
                        continue
                    
                    # Sinon, parser les balises <think>...</think> dans le contenu
                    buffer += raw_content
                    
                    # Variables pour ce chunk
                    thinking_content = ""
                    regular_content = ""
                    
                    # Parser le buffer pour extraire thinking et contenu
                    while buffer:
                        if in_thinking:
                            # Chercher la fin de la balise thinking
                            end_idx = buffer.find("</think>")
                            if end_idx != -1:
                                # Extraire le thinking jusqu'à la fermeture
                                thinking_content += buffer[:end_idx]
                                buffer = buffer[end_idx + 8:]  # len("</think>") = 8
                                in_thinking = False
                            else:
                                # Pas de fermeture trouvée, garder une partie du buffer
                                # au cas où "</think>" serait coupé entre chunks
                                safe_len = max(0, len(buffer) - 8)
                                if safe_len > 0:
                                    thinking_content += buffer[:safe_len]
                                    buffer = buffer[safe_len:]
                                break
                        else:
                            # Chercher le début d'une balise thinking
                            start_idx = buffer.find("<think>")
                            if start_idx != -1:
                                # Contenu avant la balise
                                regular_content += buffer[:start_idx]
                                buffer = buffer[start_idx + 7:]  # len("<think>") = 7
                                in_thinking = True
                            else:
                                # Pas de balise trouvée, garder une partie du buffer
                                # au cas où "<think>" serait coupé entre chunks
                                safe_len = max(0, len(buffer) - 7)
                                if safe_len > 0:
                                    regular_content += buffer[:safe_len]
                                    buffer = buffer[safe_len:]
                                break
                    
                    # Émettre le chunk si on a du contenu
                    if thinking_content or regular_content:
                        yield {
                            "message": {
                                "role": "assistant",
                                "content": regular_content,
                                "thinking": thinking_content
                            },
                            "done": False
                        }
                    
                    # Émettre un chunk final si terminé
                    if chunk.choices[0].finish_reason is not None:
                        # Vider le buffer restant
                        final_thinking = ""
                        final_content = ""
                        if buffer:
                            if in_thinking:
                                final_thinking = buffer
                            else:
                                final_content = buffer
                        
                        yield {
                            "message": {
                                "role": "assistant",
                                "content": final_content,
                                "thinking": final_thinking
                            },
                            "done": True
                        }
                    
        except Exception as e:
            raise classify_openai_error(e, self._provider_type)
    
    def _prepare_messages_with_images(
        self,
        messages: List[Dict[str, str]],
        images: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Prépare les messages avec images au format OpenAI Vision."""
        if not images or not self.supports_vision():
            return messages
        
        # Copier les messages pour ne pas modifier l'original
        prepared = []
        
        for msg in messages:
            if msg.get("role") == "user" and msg == messages[-1]:
                # Dernier message utilisateur - ajouter les images
                content_parts = [
                    {"type": "text", "text": msg.get("content", "")}
                ]
                
                for img_base64 in images:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_base64}"
                        }
                    })
                
                prepared.append({
                    "role": "user",
                    "content": content_parts
                })
            else:
                prepared.append(msg)
        
        return prepared
    
    def test_connection(self) -> Tuple[bool, str]:
        """Teste la connexion en listant les modèles."""
        try:
            models = self.list_models()
            count = len(models)
            return True, f"Connecté - {count} modèle(s) disponible(s)"
        except LLMError as e:
            return False, e.get_user_message()
        except Exception as e:
            return False, f"Erreur: {str(e)}"
    
    def supports_vision(self) -> bool:
        """Vérifie si le provider supporte les images."""
        return self._config.get("supports_vision", False)
    
    def get_default_model(self) -> Optional[str]:
        """Retourne le modèle par défaut."""
        return self._config.get("default_model")
    
    def normalize_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalise les options pour l'API OpenAI."""
        if not options:
            return {}
        
        openai_options = {}
        
        # Liste des paramètres non supportés par ce provider
        unsupported = self._config.get("unsupported_params", [])
        
        # Mapping des options
        if "temperature" in options:
            openai_options["temperature"] = float(options["temperature"])
        if "top_p" in options and "top_p" not in unsupported:
            openai_options["top_p"] = float(options["top_p"])
        if "max_tokens" in options:
            openai_options["max_tokens"] = int(options["max_tokens"])
        elif "num_ctx" in options:
            # Convertir num_ctx en max_tokens (approximatif)
            openai_options["max_tokens"] = min(int(options["num_ctx"]), 4096)
        
        # frequency_penalty - seulement si supporté
        if "frequency_penalty" not in unsupported:
            if "frequency_penalty" in options:
                openai_options["frequency_penalty"] = float(options["frequency_penalty"])
            elif "repeat_penalty" in options:
                # Convertir repeat_penalty (1-2) en frequency_penalty (0-2)
                rp = float(options["repeat_penalty"])
                openai_options["frequency_penalty"] = max(0, min(2, rp - 1))
        
        return openai_options

    def transcribe(
        self,
        file: Any,
        model: str,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Transcrit un fichier audio en texte (Structure-to-Text).
        
        Args:
            file: Fichier audio ouvert (binaire)
            model: Nom du modèle
            options: Options supplémentaires
            
        Returns:
            Le texte transcrit
        """
        try:
            client = self._get_client()
            response = client.audio.transcriptions.create(
                model=model,
                file=file
            )
            return response.text
        except Exception as e:
            raise classify_openai_error(e, self._provider_type)

    def generate_speech(
        self,
        text: str,
        model: str,
        voice: str,
        speed: float = 1.0,
        options: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Génère de la parole à partir de texte (Text-to-Speech).
        
        Args:
            text: Texte à lire
            model: Nom du modèle TTS
            voice: Nom de la voix
            speed: Vitesse de lecture
            options: Options supplémentaires
            
        Returns:
            Le contenu binaire de l'audio MP3 (response.content)
        """
        try:
            client = self._get_client()
            
            # Paramètres de base
            params = {
                "model": model,
                "voice": voice or "alloy",
                "input": text,
                "speed": speed
            }
            
            # Ajouter les options supplémentaires si fournies
            if options:
                params.update(options)
                
            response = client.audio.speech.create(**params)
            
            # Retourne le contenu binaire (streamable)
            return response.content
        except Exception as e:
            raise classify_openai_error(e, self._provider_type)
