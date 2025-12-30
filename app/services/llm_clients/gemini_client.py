"""
Client pour l'API Google Gemini.

Utilise le SDK officiel google-generativeai.
"""

from typing import List, Dict, Any, Optional, Tuple, Iterable

from .base_client import BaseLLMClient
from ..llm_error_handler import LLMError, LLMErrorType, classify_gemini_error


# Modèles Gemini disponibles
GEMINI_MODELS = [
    {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Le plus puissant, contexte de 2M tokens"},
    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "Rapide et polyvalent"},
    {"id": "gemini-1.5-flash-8b", "name": "Gemini 1.5 Flash 8B", "description": "Léger et économique"},
    {"id": "gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash (Exp)", "description": "Nouvelle génération expérimentale"},
    {"id": "gemini-pro", "name": "Gemini Pro", "description": "Version stable classique"}
]


class GeminiClient(BaseLLMClient):
    """Client pour l'API Google Gemini."""
    
    def __init__(self, api_key: str = ""):
        """
        Initialise le client Gemini.
        
        Args:
            api_key: Clé API Google AI Studio
        """
        self._api_key = api_key
        self._configured = False
    
    def _configure(self):
        """Configure le SDK Gemini."""
        if self._configured:
            return
        
        try:
            import google.generativeai as genai
        except ImportError:
            raise LLMError(
                "SDK Google Generative AI non installé. Exécutez: pip install google-generativeai",
                "gemini",
                LLMErrorType.UNKNOWN
            )
        
        genai.configure(api_key=self._api_key)
        self._configured = True
    
    def _get_model(self, model_name: str):
        """Retourne une instance du modèle Gemini."""
        self._configure()
        
        try:
            import google.generativeai as genai
            return genai.GenerativeModel(model_name)
        except Exception as e:
            raise classify_gemini_error(e)
    
    @property
    def provider_name(self) -> str:
        return "gemini"
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste des modèles Gemini disponibles.
        
        Utilise l'API pour lister les modèles dynamiquement.
        """
        self._configure()
        
        try:
            import google.generativeai as genai
            
            models = []
            for model in genai.list_models():
                if "generateContent" in model.supported_generation_methods:
                    models.append({
                        "id": model.name.replace("models/", ""),
                        "name": model.display_name,
                        "description": model.description or ""
                    })
            
            return models if models else GEMINI_MODELS.copy()
            
        except Exception as e:
            # Fallback sur la liste statique
            return GEMINI_MODELS.copy()
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Envoie une requête de chat non-streaming."""
        try:
            gemini_model = self._get_model(model)
            
            # Convertir les messages au format Gemini
            history, last_message = self._prepare_chat(messages)
            
            # Créer la config de génération
            generation_config = self._make_generation_config(options)
            
            # Créer le chat et envoyer
            chat = gemini_model.start_chat(history=history)
            response = chat.send_message(
                last_message,
                generation_config=generation_config
            )
            
            # Extraction sécurisée du texte
            content = ""
            try:
                content = response.text
            except Exception:
                # Si response.text échoue (pas de parts valides), on renvoie une chaîne vide ou on log
                # Cela peut arriver si le modèle s'arrête sans générer de texte (finish_reason)
                pass

            return {
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "done": True
            }
            
        except Exception as e:
            raise classify_gemini_error(e)
    
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        images: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Iterable[Dict[str, Any]]:
        """Envoie une requête de chat streaming."""
        try:
            gemini_model = self._get_model(model)
            
            # Convertir les messages au format Gemini
            history, last_message = self._prepare_chat(messages)
            
            # Ajouter les images au dernier message si présentes
            if images:
                last_message = self._prepare_content_with_images(last_message, images)
            
            # Créer la config de génération
            generation_config = self._make_generation_config(options)
            
            # Créer le chat et stream
            chat = gemini_model.start_chat(history=history)
            response = chat.send_message(
                last_message,
                generation_config=generation_config,
                stream=True
            )
            
            for chunk in response:
                content = ""
                try:
                    content = chunk.text
                except Exception:
                    # Ignorer les chunks sans texte valide
                    continue

                if content:
                    yield {
                        "message": {
                            "role": "assistant",
                            "content": content,
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
            raise classify_gemini_error(e)
    
    def _prepare_chat(self, messages: List[Dict[str, str]]) -> Tuple[list, str]:
        """
        Convertit les messages au format Gemini.
        
        Returns:
            Tuple (history, last_message)
        """
        try:
            from google.generativeai.types import content_types
        except ImportError:
            content_types = None
        
        history = []
        system_instruction = None
        last_user_message = ""
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = content
            elif role == "user":
                last_user_message = content
                if msg != messages[-1]:
                    history.append({
                        "role": "user",
                        "parts": [content]
                    })
            elif role == "assistant":
                history.append({
                    "role": "model",
                    "parts": [content]
                })
        
        # Préfixer le dernier message avec l'instruction système si présente
        if system_instruction and last_user_message:
            last_user_message = f"[Instructions système: {system_instruction}]\n\n{last_user_message}"
        
        return history, last_user_message
    
    def _prepare_content_with_images(self, text: str, images: List[str]) -> list:
        """Prépare le contenu avec images au format Gemini."""
        import base64
        
        try:
            from PIL import Image
            import io
        except ImportError:
            # Si PIL n'est pas disponible, retourner seulement le texte
            return text
        
        parts = [text]
        
        for img_base64 in images:
            try:
                img_bytes = base64.b64decode(img_base64)
                img = Image.open(io.BytesIO(img_bytes))
                parts.append(img)
            except Exception:
                continue
        
        return parts
    
    def _make_generation_config(self, options: Optional[Dict[str, Any]]) -> dict:
        """Crée la configuration de génération Gemini."""
        config = {}
        
        if not options:
            return config
        
        if "temperature" in options:
            config["temperature"] = float(options["temperature"])
        if "top_p" in options:
            config["top_p"] = float(options["top_p"])
        if "top_k" in options:
            config["top_k"] = int(options["top_k"])
        if "max_tokens" in options:
            config["max_output_tokens"] = int(options["max_tokens"])
        elif "num_ctx" in options:
            config["max_output_tokens"] = min(int(options["num_ctx"]), 8192)
        
        return config
    
    def test_connection(self) -> Tuple[bool, str]:
        """Teste la connexion en listant les modèles."""
        if not self._api_key:
            return False, "Clé API manquante"
        
        try:
            models = self.list_models()
            return True, f"Connecté - {len(models)} modèle(s) disponible(s)"
        except LLMError as e:
            return False, e.get_user_message()
        except Exception as e:
            return False, f"Erreur: {str(e)}"
    
    def supports_vision(self) -> bool:
        """Gemini supporte les images."""
        return True
    
    def get_default_model(self) -> Optional[str]:
        return "gemini-1.5-flash"
    
    def normalize_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalise les options (délégué à _make_generation_config)."""
        return self._make_generation_config(options)
