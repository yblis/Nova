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
        "requires_v1_suffix": True  # LM Studio nécessite /v1 dans l'URL
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
        "base_url": "https://api-inference.huggingface.co/v1",
        "default_model": "mistralai/Mistral-7B-Instruct-v0.3",
        "supports_vision": False,
        "unsupported_params": ["frequency_penalty", "presence_penalty"]
    },
    "openai_compatible": {
        "base_url": "",  # L'utilisateur doit fournir l'URL
        "default_model": None,  # Dépend du provider
        "supports_vision": True,
        "default_api_key": "not-needed",  # Certains providers locaux n'ont pas besoin de clé
        "requires_v1_suffix": True  # La plupart des API compatibles OpenAI utilisent /v1
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
        
        try:
            client = self._get_client()
            response = client.models.list()
            
            models = []
            for model in response.data:
                models.append({
                    "id": model.id,
                    "name": model.id,
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
    
    def _list_models_lmstudio_native(self) -> List[Dict[str, Any]]:
        """Liste tous les modèles LM Studio via l'API native /api/v0/models."""
        try:
            import httpx
            
            # Construire l'URL de base sans /v1 pour l'API native LM Studio
            base_url = self._base_url
            if base_url.endswith('/v1'):
                base_url = base_url[:-3]
            
            url = f"{base_url}/api/v0/models"
            
            with httpx.Client(timeout=5.0) as http_client:
                response = http_client.get(url)
                response.raise_for_status()
                response_data = response.json()
            
            # L'API retourne {"object": "list", "data": [...]}
            models_list = response_data.get("data", []) if isinstance(response_data, dict) else response_data
            
            models = []
            for model in models_list:
                if isinstance(model, dict):
                    models.append({
                        "id": model.get("id", ""),
                        "name": model.get("id", "Unknown"),
                        "quantization": model.get("quantization", ""),
                        "arch": model.get("arch", ""),
                        "type": model.get("type", "llm"),
                        "state": model.get("state", "not-loaded"),
                        "max_context_length": model.get("max_context_length", 0),
                        "publisher": model.get("publisher", ""),
                        "compatibility_type": model.get("compatibility_type", "")
                    })
            
            # Trier par nom
            models.sort(key=lambda x: x["name"])
            
            return models
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to list LM Studio models via native API: {e}")
            # Fallback to OpenAI compatible API
            try:
                client = self._get_client()
                response = client.models.list()
                return [{"id": m.id, "name": m.id} for m in response.data]
            except Exception:
                return []
    
    def list_loaded_models(self) -> List[Dict[str, Any]]:
        """
        Liste les modèles actuellement chargés en mémoire.
        
        Disponible uniquement pour LM Studio via l'API native /api/v0/models.
        
        Returns:
            Liste des modèles chargés avec leurs informations
        """
        if self._provider_type != "lmstudio":
            return []
        
        try:
            import httpx
            
            # Construire l'URL de base sans /v1 pour l'API native LM Studio
            base_url = self._base_url
            if base_url.endswith('/v1'):
                base_url = base_url[:-3]
            
            url = f"{base_url}/api/v0/models"
            
            with httpx.Client(timeout=5.0) as http_client:
                response = http_client.get(url)
                response.raise_for_status()
                response_data = response.json()
            
            # L'API retourne {"object": "list", "data": [...]}
            models_list = response_data.get("data", []) if isinstance(response_data, dict) else response_data
            
            # Filtrer les modèles avec state="loaded"
            loaded_models = []
            for model in models_list:
                if isinstance(model, dict) and model.get("state") == "loaded":
                    loaded_models.append({
                        "name": model.get("id", "Unknown"),
                        "id": model.get("id", ""),
                        "size": 0,  # L'API v0 ne retourne pas la taille en bytes
                        "context_length": model.get("max_context_length", 0),
                        "quantization": model.get("quantization", ""),
                        "arch": model.get("arch", ""),
                        "type": model.get("type", "llm"),
                        "provider": "lmstudio"
                    })
            
            return loaded_models
            
        except Exception as e:
            # Log l'erreur mais ne pas lever d'exception
            import logging
            logging.getLogger(__name__).warning(f"Failed to list loaded LM Studio models: {e}")
            return []
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Envoie une requête de chat non-streaming."""
        try:
            client = self._get_client()
            normalized_opts = self.normalize_options(options)
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
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
        """Envoie une requête de chat streaming."""
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
            
            for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    content = delta.content or ""
                    
                    yield {
                        "message": {
                            "role": "assistant",
                            "content": content,
                            "thinking": ""
                        },
                        "done": chunk.choices[0].finish_reason is not None
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
