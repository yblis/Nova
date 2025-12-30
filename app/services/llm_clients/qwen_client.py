"""
Client pour l'API Qwen (Alibaba DashScope).

Utilise le SDK officiel dashscope.
"""

from typing import List, Dict, Any, Optional, Tuple, Iterable

from .base_client import BaseLLMClient
from ..llm_error_handler import LLMError, LLMErrorType


# Modèles Qwen disponibles
QWEN_MODELS = [
    {"id": "qwen-max", "name": "Qwen Max", "description": "Le plus puissant, idéal pour les tâches complexes"},
    {"id": "qwen-plus", "name": "Qwen Plus", "description": "Équilibre performance/coût"},
    {"id": "qwen-turbo", "name": "Qwen Turbo", "description": "Rapide et économique"},
    {"id": "qwen-long", "name": "Qwen Long", "description": "Contexte très long (10M tokens)"},
    {"id": "qwen-vl-max", "name": "Qwen VL Max", "description": "Vision-Language, multimodal avancé"},
    {"id": "qwen-vl-plus", "name": "Qwen VL Plus", "description": "Vision-Language, équilibré"}
]


class QwenClient(BaseLLMClient):
    """Client pour l'API Qwen (DashScope)."""
    
    def __init__(self, api_key: str = ""):
        """
        Initialise le client Qwen.
        
        Args:
            api_key: Clé API DashScope (Alibaba Cloud)
        """
        self._api_key = api_key
        self._configured = False
    
    def _configure(self):
        """Configure le SDK DashScope."""
        if self._configured:
            return
        
        try:
            import dashscope
        except ImportError:
            raise LLMError(
                "SDK DashScope non installé. Exécutez: pip install dashscope",
                "qwen",
                LLMErrorType.UNKNOWN
            )
        
        dashscope.api_key = self._api_key
        self._configured = True
    
    @property
    def provider_name(self) -> str:
        return "qwen"
    
    def list_models(self) -> List[Dict[str, Any]]:
        """Retourne la liste des modèles Qwen disponibles."""
        # DashScope ne fournit pas d'endpoint pour lister les modèles
        return QWEN_MODELS.copy()
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Envoie une requête de chat non-streaming."""
        self._configure()
        
        try:
            from dashscope import Generation
            
            # Convertir les messages au format DashScope
            dashscope_messages = self._prepare_messages(messages)
            
            # Paramètres de génération
            params = self._make_generation_params(options)
            
            response = Generation.call(
                model=model,
                messages=dashscope_messages,
                result_format='message',
                **params
            )
            
            if response.status_code != 200:
                raise LLMError(
                    response.message,
                    "qwen",
                    self._classify_error_code(response.code),
                    http_status=response.status_code
                )
            
            content = ""
            if response.output and response.output.choices:
                content = response.output.choices[0].message.content
            
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
            
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(str(e), "qwen", LLMErrorType.UNKNOWN)
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        images: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Iterable[Dict[str, Any]]:
        """Envoie une requête de chat streaming."""
        self._configure()
        
        try:
            from dashscope import Generation
            
            # Convertir les messages au format DashScope
            dashscope_messages = self._prepare_messages(messages)
            
            # Ajouter les images si présentes (pour modèles VL)
            if images and model.startswith("qwen-vl"):
                dashscope_messages = self._prepare_messages_with_images(
                    dashscope_messages, images
                )
            
            # Paramètres de génération
            params = self._make_generation_params(options)
            
            responses = Generation.call(
                model=model,
                messages=dashscope_messages,
                result_format='message',
                stream=True,
                incremental_output=True,
                **params
            )
            
            for response in responses:
                if response.status_code != 200:
                    raise LLMError(
                        response.message,
                        "qwen",
                        self._classify_error_code(response.code),
                        http_status=response.status_code
                    )
                
                content = ""
                if response.output and response.output.choices:
                    content = response.output.choices[0].message.content or ""
                
                is_done = response.output.choices[0].finish_reason == "stop" if response.output.choices else False
                
                yield {
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "thinking": ""
                    },
                    "done": is_done
                }
            
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(str(e), "qwen", LLMErrorType.UNKNOWN)
    
    def _prepare_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Convertit les messages au format DashScope."""
        # DashScope utilise le même format que OpenAI
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]
    
    def _prepare_messages_with_images(
        self,
        messages: List[Dict[str, str]],
        images: List[str]
    ) -> List[Dict[str, Any]]:
        """Prépare les messages avec images pour les modèles Qwen-VL."""
        prepared = []
        
        for msg in messages:
            if msg.get("role") == "user" and msg == messages[-1]:
                # Format Qwen-VL pour les images
                content = [
                    {"text": msg.get("content", "")}
                ]
                
                for img_base64 in images:
                    content.append({
                        "image": f"data:image/jpeg;base64,{img_base64}"
                    })
                
                prepared.append({
                    "role": "user",
                    "content": content
                })
            else:
                prepared.append(msg)
        
        return prepared
    
    def _make_generation_params(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Crée les paramètres de génération DashScope."""
        params = {}
        
        if not options:
            return params
        
        if "temperature" in options:
            params["temperature"] = float(options["temperature"])
        if "top_p" in options:
            params["top_p"] = float(options["top_p"])
        if "top_k" in options:
            params["top_k"] = int(options["top_k"])
        if "max_tokens" in options:
            params["max_tokens"] = int(options["max_tokens"])
        elif "num_ctx" in options:
            params["max_tokens"] = min(int(options["num_ctx"]), 8192)
        if "repeat_penalty" in options:
            params["repetition_penalty"] = float(options["repeat_penalty"])
        
        return params
    
    def _classify_error_code(self, code: str) -> LLMErrorType:
        """Classifie un code d'erreur DashScope."""
        code_lower = code.lower() if code else ""
        
        if "invalid" in code_lower or "auth" in code_lower:
            return LLMErrorType.AUTH_ERROR
        elif "rate" in code_lower or "limit" in code_lower:
            return LLMErrorType.RATE_LIMIT
        elif "model" in code_lower or "not_found" in code_lower:
            return LLMErrorType.MODEL_NOT_FOUND
        elif "context" in code_lower or "length" in code_lower:
            return LLMErrorType.CONTEXT_LENGTH
        else:
            return LLMErrorType.UNKNOWN
    
    def test_connection(self) -> Tuple[bool, str]:
        """Teste la connexion en envoyant une requête minimale."""
        if not self._api_key:
            return False, "Clé API manquante"
        
        try:
            self._configure()
            from dashscope import Generation
            
            response = Generation.call(
                model="qwen-turbo",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            
            if response.status_code == 200:
                return True, "Connecté à DashScope (Qwen)"
            else:
                return False, f"Erreur: {response.message}"
                
        except LLMError as e:
            return False, e.get_user_message()
        except Exception as e:
            return False, f"Erreur: {str(e)}"
    
    def supports_vision(self) -> bool:
        """Les modèles Qwen-VL supportent les images."""
        return True
    
    def get_default_model(self) -> Optional[str]:
        return "qwen-plus"
    
    def normalize_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalise les options (délégué à _make_generation_params)."""
        return self._make_generation_params(options)
