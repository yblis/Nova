"""
Client pour l'API Google Gemini.

Utilise le nouveau SDK officiel google-genai (anciennement google-generativeai).
"""

from typing import List, Dict, Any, Optional, Tuple, Iterable

from .base_client import BaseLLMClient
from ..llm_error_handler import LLMError, LLMErrorType, classify_gemini_error


# Modèles Gemini disponibles (fallback)
GEMINI_MODELS = [
    {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "description": "Dernière génération, rapide et puissant"},
    {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite", "description": "Version légère et économique"},
    {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "description": "Le plus puissant, contexte de 2M tokens"},
    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "description": "Rapide et polyvalent"},
    {"id": "gemini-1.5-flash-8b", "name": "Gemini 1.5 Flash 8B", "description": "Léger et économique"},
]


class GeminiClient(BaseLLMClient):
    """Client pour l'API Google Gemini utilisant le nouveau SDK google-genai."""
    
    def __init__(self, api_key: str = ""):
        """
        Initialise le client Gemini.
        
        Args:
            api_key: Clé API Google AI Studio
        """
        self._api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Retourne le client Gemini, en le créant si nécessaire."""
        if self._client is not None:
            return self._client
        
        try:
            from google import genai
        except ImportError:
            raise LLMError(
                "SDK Google GenAI non installé. Exécutez: pip install google-genai",
                "gemini",
                LLMErrorType.UNKNOWN
            )
        
        self._client = genai.Client(api_key=self._api_key)
        return self._client
    
    @property
    def provider_name(self) -> str:
        return "gemini"
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste des modèles Gemini disponibles.
        
        Utilise l'API pour lister les modèles dynamiquement.
        """
        try:
            client = self._get_client()
            
            models = []
            for model in client.models.list():
                # Vérifier si le modèle supporte la génération de contenu
                if hasattr(model, 'supported_actions') and model.supported_actions:
                    if 'generateContent' not in model.supported_actions:
                        continue
                
                model_id = model.name.replace("models/", "") if model.name else ""
                display_name = getattr(model, 'display_name', model_id)
                description = getattr(model, 'description', "") or ""
                
                models.append({
                    "id": model_id,
                    "name": display_name,
                    "description": description
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
            client = self._get_client()
            
            # Convertir les messages au format Gemini
            contents, system_instruction = self._prepare_contents(messages)
            
            # Créer la config de génération
            config = self._make_generation_config(options, system_instruction)
            
            # Générer le contenu
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
            
            # Extraction sécurisée du texte
            content = ""
            try:
                content = response.text
            except Exception:
                # Si response.text échoue (pas de parts valides), on renvoie une chaîne vide
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
            client = self._get_client()
            
            # Convertir les messages au format Gemini
            contents, system_instruction = self._prepare_contents(messages)
            
            # Ajouter les images au dernier message si présentes
            if images and contents:
                contents = self._add_images_to_contents(contents, images)
            
            # Créer la config de génération
            config = self._make_generation_config(options, system_instruction)
            
            # Stream du contenu
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config
            ):
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
    
    def _prepare_contents(self, messages: List[Dict[str, str]]) -> Tuple[list, Optional[str]]:
        """
        Convertit les messages au format Gemini nouveau SDK.
        
        Returns:
            Tuple (contents, system_instruction)
        """
        try:
            from google.genai import types
        except ImportError:
            types = None
        
        contents = []
        system_instruction = None
        
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "system":
                system_instruction = content
            elif role == "user":
                if types:
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part(text=content)]
                    ))
                else:
                    contents.append({
                        "role": "user",
                        "parts": [{"text": content}]
                    })
            elif role == "assistant":
                if types:
                    contents.append(types.Content(
                        role="model",
                        parts=[types.Part(text=content)]
                    ))
                else:
                    contents.append({
                        "role": "model",
                        "parts": [{"text": content}]
                    })
        
        return contents, system_instruction
    
    def _add_images_to_contents(self, contents: list, images: List[str]) -> list:
        """Ajoute des images au dernier message utilisateur."""
        import base64
        
        try:
            from google.genai import types
        except ImportError:
            return contents
        
        if not contents:
            return contents
        
        # Trouver le dernier message utilisateur
        for i in range(len(contents) - 1, -1, -1):
            content = contents[i]
            role = content.role if hasattr(content, 'role') else content.get('role')
            if role == "user":
                # Ajouter les images comme parts
                parts = list(content.parts) if hasattr(content, 'parts') else list(content.get('parts', []))
                
                for img_base64 in images:
                    try:
                        img_bytes = base64.b64decode(img_base64)
                        # Détecter le type MIME
                        mime_type = "image/jpeg"
                        if img_base64.startswith("/9j/"):
                            mime_type = "image/jpeg"
                        elif img_base64.startswith("iVBOR"):
                            mime_type = "image/png"
                        elif img_base64.startswith("R0lGOD"):
                            mime_type = "image/gif"
                        elif img_base64.startswith("UklGR"):
                            mime_type = "image/webp"
                        
                        parts.append(types.Part(
                            inline_data=types.Blob(
                                mime_type=mime_type,
                                data=img_bytes
                            )
                        ))
                    except Exception:
                        continue
                
                # Remplacer le content avec les nouvelles parts
                contents[i] = types.Content(role="user", parts=parts)
                break
        
        return contents
    
    def _make_generation_config(
        self, 
        options: Optional[Dict[str, Any]], 
        system_instruction: Optional[str] = None
    ) -> Any:
        """Crée la configuration de génération Gemini."""
        try:
            from google.genai import types
        except ImportError:
            return None
        
        config_kwargs = {}
        
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        
        if options:
            if "temperature" in options:
                config_kwargs["temperature"] = float(options["temperature"])
            if "top_p" in options:
                config_kwargs["top_p"] = float(options["top_p"])
            if "top_k" in options:
                config_kwargs["top_k"] = int(options["top_k"])
            if "max_tokens" in options:
                config_kwargs["max_output_tokens"] = int(options["max_tokens"])
            elif "num_ctx" in options:
                config_kwargs["max_output_tokens"] = min(int(options["num_ctx"]), 8192)
        
        if config_kwargs:
            return types.GenerateContentConfig(**config_kwargs)
        
        return None
    
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
        return "gemini-2.0-flash"
    
    def normalize_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalise les options."""
        if not options:
            return {}
        
        normalized = {}
        if "temperature" in options:
            normalized["temperature"] = float(options["temperature"])
        if "top_p" in options:
            normalized["top_p"] = float(options["top_p"])
        if "top_k" in options:
            normalized["top_k"] = int(options["top_k"])
        if "max_tokens" in options:
            normalized["max_output_tokens"] = int(options["max_tokens"])
        elif "num_ctx" in options:
            normalized["max_output_tokens"] = min(int(options["num_ctx"]), 8192)
        
        return normalized
