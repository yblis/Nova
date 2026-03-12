"""
Client pour l'API Anthropic (Claude).

Utilise le SDK officiel anthropic.
L'API Anthropic a un format différent d'OpenAI (system séparé des messages).
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Iterable

from .base_client import BaseLLMClient
from ..llm_error_handler import LLMError, LLMErrorType, classify_anthropic_error

logger = logging.getLogger(__name__)


class AnthropicClient(BaseLLMClient):
    """Client pour l'API Anthropic (Claude)."""
    
    def __init__(self, api_key: str = ""):
        """
        Initialise le client Anthropic.
        
        Args:
            api_key: Clé API Anthropic
        """
        self._api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Retourne le client Anthropic (lazy loading)."""
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError:
                raise LLMError(
                    "SDK Anthropic non installé. Exécutez: pip install anthropic",
                    "anthropic",
                    LLMErrorType.UNKNOWN
                )
            
            self._client = Anthropic(api_key=self._api_key)
        
        return self._client
    
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste des modèles Claude disponibles.
        
        Utilise l'endpoint /v1/models de l'API Anthropic.
        Retourne une liste vide en cas d'échec.
        """
        try:
            client = self._get_client()
            response = client.models.list()

            models = []
            for model in response.data:
                model_id = model.id
                display_name = getattr(model, 'display_name', model_id) or model_id
                description = getattr(model, 'description', "") or ""

                models.append({
                    "id": model_id,
                    "name": display_name,
                    "description": description
                })

            models.sort(key=lambda x: x["name"])
            return models

        except Exception as e:
            logger.warning("Failed to list Anthropic models from API: %s", e)
            return []
    
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
            
            # Séparer le system prompt des messages
            system_prompt, chat_messages = self._extract_system_prompt(messages)
            
            # Ajouter les images au dernier message si présentes
            if images:
                chat_messages = self._prepare_messages_with_images(chat_messages, images)
            
            normalized_opts = self.normalize_options(options)
            
            response = client.messages.create(
                model=model,
                system=system_prompt if system_prompt else None,
                messages=chat_messages,
                max_tokens=normalized_opts.get("max_tokens", 4096),
                **{k: v for k, v in normalized_opts.items() if k != "max_tokens"}
            )
            
            # Extraire le contenu de la réponse
            content = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, 'text'):
                        content += block.text
            
            return {
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "done": True,
                "usage": {
                    "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                    "completion_tokens": response.usage.output_tokens if response.usage else 0
                }
            }
            
        except Exception as e:
            raise classify_anthropic_error(e)
    
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
            
            # Séparer le system prompt des messages
            system_prompt, chat_messages = self._extract_system_prompt(messages)
            
            # Ajouter les images au dernier message si présentes
            if images:
                chat_messages = self._prepare_messages_with_images(chat_messages, images)
            
            normalized_opts = self.normalize_options(options)
            
            with client.messages.stream(
                model=model,
                system=system_prompt if system_prompt else None,
                messages=chat_messages,
                max_tokens=normalized_opts.get("max_tokens", 4096),
                **{k: v for k, v in normalized_opts.items() if k != "max_tokens"}
            ) as stream:
                for text in stream.text_stream:
                    yield {
                        "message": {
                            "role": "assistant",
                            "content": text,
                            "thinking": ""
                        },
                        "done": False
                    }
                
                # Message final
                yield {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "thinking": ""
                    },
                    "done": True
                }
                    
        except Exception as e:
            raise classify_anthropic_error(e)
    
    def _extract_system_prompt(
        self,
        messages: List[Dict[str, str]]
    ) -> Tuple[str, List[Dict[str, str]]]:
        """
        Extrait le system prompt des messages.
        
        Anthropic requiert que le system prompt soit séparé.
        
        Returns:
            Tuple (system_prompt, messages_sans_system)
        """
        system_prompt = ""
        chat_messages = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            else:
                chat_messages.append(msg)
        
        return system_prompt, chat_messages
    
    def _prepare_messages_with_images(
        self,
        messages: List[Dict[str, str]],
        images: List[str]
    ) -> List[Dict[str, Any]]:
        """Prépare les messages avec images au format Anthropic."""
        if not images:
            return messages
        
        prepared = []
        
        for msg in messages:
            if msg.get("role") == "user" and msg == messages[-1]:
                # Format Anthropic pour les images
                content = [
                    {"type": "text", "text": msg.get("content", "")}
                ]
                
                for img_base64 in images:
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_base64
                        }
                    })
                
                prepared.append({
                    "role": "user",
                    "content": content
                })
            else:
                prepared.append(msg)
        
        return prepared
    
    def test_connection(self) -> Tuple[bool, str]:
        """Teste la connexion en listant les modèles disponibles."""
        if not self._api_key:
            return False, "Clé API manquante"
        
        try:
            models = self.list_models()
            return True, f"Connecté - {len(models)} modèle(s) disponible(s)"
        except LLMError as e:
            return False, e.get_user_message()
        except Exception as e:
            error_str = str(e).lower()
            if "invalid" in error_str or "api key" in error_str:
                return False, "Clé API invalide"
            return False, f"Erreur: {str(e)}"
    
    def supports_vision(self) -> bool:
        """Claude supporte les images."""
        return True
    
    def get_default_model(self) -> Optional[str]:
        return None
    
    def normalize_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalise les options pour l'API Anthropic."""
        if not options:
            return {"max_tokens": 4096}
        
        anthropic_options = {"max_tokens": 4096}
        
        if "temperature" in options:
            anthropic_options["temperature"] = float(options["temperature"])
        if "top_p" in options:
            anthropic_options["top_p"] = float(options["top_p"])
        if "top_k" in options:
            anthropic_options["top_k"] = int(options["top_k"])
        if "max_tokens" in options:
            anthropic_options["max_tokens"] = int(options["max_tokens"])
        elif "num_ctx" in options:
            anthropic_options["max_tokens"] = min(int(options["num_ctx"]), 4096)
        
        return anthropic_options
