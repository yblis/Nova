"""
Client pour l'API Cohere v2.

Implémente l'interface Cohere pour les modèles Command R, Command R+, etc.
"""

from typing import List, Dict, Any, Optional, Tuple, Iterable
import httpx

from .base_client import BaseLLMClient
from ..llm_error_handler import LLMError, LLMErrorType


class CohereClient(BaseLLMClient):
    """Client pour l'API Cohere v2."""
    
    BASE_URL = "https://api.cohere.ai/v2"
    
    def __init__(self, api_key: str = ""):
        """
        Initialise le client Cohere.
        
        Args:
            api_key: Clé API Cohere
        """
        self._api_key = api_key
        self._timeout = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)
    
    def _get_headers(self) -> Dict[str, str]:
        """Retourne les headers pour les requêtes API."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    @property
    def provider_name(self) -> str:
        return "cohere"
    
    def list_models(self) -> List[Dict[str, Any]]:
        """Liste les modèles disponibles."""
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(
                    "https://api.cohere.ai/v1/models",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                data = response.json()
                
                models = []
                for model in data.get("models", []):
                    # Filtrer pour ne garder que les modèles de chat
                    endpoints = model.get("endpoints", [])
                    if "chat" in endpoints:
                        models.append({
                            "id": model.get("name", ""),
                            "name": model.get("name", ""),
                            "description": model.get("description", ""),
                            "context_length": model.get("context_length", 0),
                            "tokenizer_url": model.get("tokenizer_url", "")
                        })
                
                # Trier par nom
                models.sort(key=lambda x: x["name"])
                return models
                
        except httpx.HTTPStatusError as e:
            raise self._classify_error(e)
        except Exception as e:
            raise LLMError(
                f"Erreur lors de la liste des modèles: {str(e)}",
                "cohere",
                LLMErrorType.CONNECTION_ERROR
            )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Envoie une requête de chat non-streaming."""
        try:
            # Préparer les messages au format Cohere v2
            cohere_messages = self._convert_messages(messages)
            
            payload = {
                "model": model,
                "messages": cohere_messages
            }
            
            # Ajouter les options
            if options:
                if "temperature" in options:
                    payload["temperature"] = float(options["temperature"])
                if "max_tokens" in options:
                    payload["max_tokens"] = int(options["max_tokens"])
                if "top_p" in options:
                    payload["p"] = float(options["top_p"])
                if "top_k" in options:
                    payload["k"] = int(options["top_k"])
            
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self.BASE_URL}/chat",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                # Extraire le contenu de la réponse
                content = ""
                message_data = data.get("message", {})
                for item in message_data.get("content", []):
                    if item.get("type") == "text":
                        content += item.get("text", "")
                
                return {
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "done": True,
                    "usage": {
                        "prompt_tokens": data.get("usage", {}).get("billed_units", {}).get("input_tokens", 0),
                        "completion_tokens": data.get("usage", {}).get("billed_units", {}).get("output_tokens", 0),
                        "total_tokens": (
                            data.get("usage", {}).get("billed_units", {}).get("input_tokens", 0) +
                            data.get("usage", {}).get("billed_units", {}).get("output_tokens", 0)
                        )
                    }
                }
                
        except httpx.HTTPStatusError as e:
            raise self._classify_error(e)
        except Exception as e:
            raise LLMError(
                f"Erreur lors du chat: {str(e)}",
                "cohere",
                LLMErrorType.UNKNOWN
            )
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        images: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Iterable[Dict[str, Any]]:
        """Envoie une requête de chat streaming."""
        try:
            # Préparer les messages au format Cohere v2
            cohere_messages = self._convert_messages(messages)
            
            payload = {
                "model": model,
                "messages": cohere_messages,
                "stream": True
            }
            
            # Ajouter les options
            if options:
                if "temperature" in options:
                    payload["temperature"] = float(options["temperature"])
                if "max_tokens" in options:
                    payload["max_tokens"] = int(options["max_tokens"])
                if "top_p" in options:
                    payload["p"] = float(options["top_p"])
                if "top_k" in options:
                    payload["k"] = int(options["top_k"])
            
            with httpx.Client(timeout=self._timeout) as client:
                with client.stream(
                    "POST",
                    f"{self.BASE_URL}/chat",
                    headers=self._get_headers(),
                    json=payload
                ) as response:
                    response.raise_for_status()
                    
                    for line in response.iter_lines():
                        if not line:
                            continue
                        
                        # Cohere utilise SSE, les lignes commencent par "data: "
                        if line.startswith("data: "):
                            line = line[6:]
                        
                        try:
                            import json
                            event = json.loads(line)
                            event_type = event.get("type", "")
                            
                            if event_type == "content-delta":
                                delta = event.get("delta", {})
                                content = delta.get("message", {}).get("content", {}).get("text", "")
                                
                                yield {
                                    "message": {
                                        "role": "assistant",
                                        "content": content,
                                        "thinking": ""
                                    },
                                    "done": False
                                }
                            
                            elif event_type == "message-end":
                                yield {
                                    "message": {
                                        "role": "assistant",
                                        "content": "",
                                        "thinking": ""
                                    },
                                    "done": True
                                }
                                
                        except json.JSONDecodeError:
                            continue
                            
        except httpx.HTTPStatusError as e:
            raise self._classify_error(e)
        except Exception as e:
            raise LLMError(
                f"Erreur lors du streaming: {str(e)}",
                "cohere",
                LLMErrorType.UNKNOWN
            )
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Convertit les messages au format Cohere v2.
        
        Le format Cohere v2 utilise:
        - role: "user", "assistant", "system", "tool"
        - content: string ou array d'objets avec type "text"
        """
        cohere_messages = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Cohere v2 supporte les mêmes rôles
            cohere_messages.append({
                "role": role,
                "content": content
            })
        
        return cohere_messages
    
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
        """Cohere ne supporte pas encore les images via cette API."""
        return False
    
    def get_default_model(self) -> Optional[str]:
        """Retourne le modèle par défaut."""
        return "command-r-plus"
    
    def _classify_error(self, e: httpx.HTTPStatusError) -> LLMError:
        """Classifie une erreur HTTP en LLMError."""
        status = e.response.status_code
        
        try:
            error_data = e.response.json()
            message = error_data.get("message", str(e))
        except Exception:
            message = str(e)
        
        if status == 401:
            return LLMError(
                f"Clé API invalide: {message}",
                "cohere",
                LLMErrorType.AUTH_ERROR
            )
        elif status == 429:
            return LLMError(
                f"Limite de requêtes atteinte: {message}",
                "cohere",
                LLMErrorType.RATE_LIMIT
            )
        elif status == 400:
            return LLMError(
                f"Requête invalide: {message}",
                "cohere",
                LLMErrorType.INVALID_REQUEST
            )
        elif status >= 500:
            return LLMError(
                f"Erreur serveur Cohere: {message}",
                "cohere",
                LLMErrorType.SERVER_ERROR
            )
        else:
            return LLMError(
                f"Erreur Cohere ({status}): {message}",
                "cohere",
                LLMErrorType.UNKNOWN
            )
