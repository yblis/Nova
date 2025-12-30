"""
Adaptateur Ollama implémentant l'interface BaseLLMClient.

Wrap l'OllamaClient existant pour respecter l'interface commune.
"""

from typing import List, Dict, Any, Optional, Tuple, Iterable
import httpx

from .base_client import BaseLLMClient
from ..llm_error_handler import LLMError, LLMErrorType


class OllamaAdapter(BaseLLMClient):
    """Client Ollama adapté à l'interface BaseLLMClient."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        connect_timeout: float = 10.0,
        read_timeout: float = 300.0
    ):
        """
        Initialise l'adaptateur Ollama.
        
        Args:
            base_url: URL du serveur Ollama
            connect_timeout: Timeout de connexion
            read_timeout: Timeout de lecture
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=read_timeout,
            pool=connect_timeout
        )
    
    @property
    def provider_name(self) -> str:
        return "ollama"
    
    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout)
    
    def list_models(self) -> List[Dict[str, Any]]:
        """Liste les modèles Ollama installés."""
        try:
            with self._client() as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                
                models = []
                for model in data.get("models", []):
                    models.append({
                        "id": model.get("name", ""),
                        "name": model.get("name", ""),
                        "description": f"Size: {self._format_size(model.get('size', 0))}",
                        "size": model.get("size", 0),
                        "modified_at": model.get("modified_at", ""),
                        "details": model.get("details", {})
                    })
                
                return models
                
        except httpx.ConnectError as e:
            raise LLMError(
                f"Impossible de se connecter à Ollama: {e}",
                self.provider_name,
                LLMErrorType.CONNECTION_ERROR
            )
        except Exception as e:
            raise LLMError(str(e), self.provider_name, LLMErrorType.UNKNOWN)
    
    def _format_size(self, size_bytes: int) -> str:
        """Formate une taille en bytes en format lisible."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Envoie une requête de chat non-streaming."""
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        
        if options:
            payload["options"] = self.normalize_options(options)
        
        try:
            with self._client() as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                
                return {
                    "message": data.get("message", {"role": "assistant", "content": ""}),
                    "done": True,
                    "total_duration": data.get("total_duration"),
                    "eval_count": data.get("eval_count")
                }
                
        except httpx.ConnectError as e:
            raise LLMError(str(e), self.provider_name, LLMErrorType.CONNECTION_ERROR)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMError(f"Modèle '{model}' non trouvé", self.provider_name, LLMErrorType.MODEL_NOT_FOUND)
            raise LLMError(str(e), self.provider_name, LLMErrorType.SERVER_ERROR)
        except Exception as e:
            raise LLMError(str(e), self.provider_name, LLMErrorType.UNKNOWN)
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        images: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Iterable[Dict[str, Any]]:
        """Envoie une requête de chat streaming."""
        import json
        
        url = f"{self.base_url}/api/chat"
        
        # Si des images sont fournies, les attacher au dernier message utilisateur
        if images and messages:
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    messages[i]["images"] = images
                    break
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        
        if options:
            payload["options"] = self.normalize_options(options)
        
        try:
            with self._client() as client:
                with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                msg = chunk.get("message", {})
                                
                                yield {
                                    "message": {
                                        "role": msg.get("role", "assistant"),
                                        "content": msg.get("content", ""),
                                        "thinking": msg.get("thinking", "")
                                    },
                                    "done": chunk.get("done", False)
                                }
                            except json.JSONDecodeError:
                                continue
                                
        except httpx.ConnectError as e:
            raise LLMError(str(e), self.provider_name, LLMErrorType.CONNECTION_ERROR)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise LLMError(f"Modèle '{model}' non trouvé", self.provider_name, LLMErrorType.MODEL_NOT_FOUND)
            raise LLMError(str(e), self.provider_name, LLMErrorType.SERVER_ERROR)
        except Exception as e:
            raise LLMError(str(e), self.provider_name, LLMErrorType.UNKNOWN)
    
    def test_connection(self) -> Tuple[bool, str]:
        """Teste la connexion au serveur Ollama."""
        try:
            with self._client() as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                model_count = len(data.get("models", []))
                return True, f"Connecté - {model_count} modèle(s) disponible(s)"
        except httpx.ConnectError:
            return False, f"Impossible de se connecter à {self.base_url}"
        except httpx.HTTPStatusError as e:
            return False, f"Erreur HTTP: {e.response.status_code}"
        except Exception as e:
            return False, f"Erreur: {str(e)}"
    
    def supports_vision(self) -> bool:
        """Ollama supporte les images avec les modèles vision (llava, etc.)."""
        return True
    
    def normalize_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalise les options pour Ollama."""
        if not options:
            return {}
        
        # Ollama utilise les mêmes noms que nos options standards
        ollama_options = {}
        
        if "temperature" in options:
            ollama_options["temperature"] = float(options["temperature"])
        if "top_p" in options:
            ollama_options["top_p"] = float(options["top_p"])
        if "top_k" in options:
            ollama_options["top_k"] = int(options["top_k"])
        if "num_ctx" in options:
            ollama_options["num_ctx"] = int(options["num_ctx"])
        if "repeat_penalty" in options:
            ollama_options["repeat_penalty"] = float(options["repeat_penalty"])
        
        return ollama_options
