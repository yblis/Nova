"""
Gestionnaire d'erreurs unifié pour les fournisseurs LLM.

Normalise les erreurs de différents fournisseurs en types d'erreurs communs.
"""

from enum import Enum
from typing import Optional, Dict, Any


class LLMErrorType(Enum):
    """Types d'erreurs LLM unifiés."""
    CONNECTION_ERROR = "connection_error"  # Impossible de se connecter
    AUTH_ERROR = "auth_error"              # Clé API invalide ou manquante
    RATE_LIMIT = "rate_limit"              # Limite de requêtes atteinte
    MODEL_NOT_FOUND = "model_not_found"    # Modèle inexistant
    CONTEXT_LENGTH = "context_length"      # Message trop long
    CONTENT_FILTER = "content_filter"      # Contenu bloqué par filtre
    SERVER_ERROR = "server_error"          # Erreur serveur (5xx)
    TIMEOUT = "timeout"                    # Timeout de la requête
    INVALID_REQUEST = "invalid_request"    # Requête mal formée
    QUOTA_EXCEEDED = "quota_exceeded"      # Quota dépassé
    UNKNOWN = "unknown"                    # Erreur inconnue


class LLMError(Exception):
    """
    Exception unifiée pour les erreurs LLM.
    
    Attributes:
        message: Message d'erreur lisible
        provider: Nom du fournisseur (ollama, openai, etc.)
        error_type: Type d'erreur normalisé
        http_status: Code HTTP si applicable
        original_error: L'erreur originale si disponible
        details: Détails supplémentaires
    """
    
    def __init__(
        self,
        message: str,
        provider: str,
        error_type: LLMErrorType = LLMErrorType.UNKNOWN,
        http_status: Optional[int] = None,
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.error_type = error_type
        self.http_status = http_status
        self.original_error = original_error
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'erreur en dictionnaire pour l'API."""
        return {
            "error": True,
            "message": self.message,
            "provider": self.provider,
            "error_type": self.error_type.value,
            "http_status": self.http_status,
            "details": self.details
        }
    
    def get_user_message(self) -> str:
        """Retourne un message utilisateur friendly."""
        messages = {
            LLMErrorType.CONNECTION_ERROR: f"Impossible de se connecter à {self.provider}. Vérifiez l'URL et la disponibilité du service.",
            LLMErrorType.AUTH_ERROR: f"Authentification échouée pour {self.provider}. Vérifiez votre clé API.",
            LLMErrorType.RATE_LIMIT: f"Limite de requêtes atteinte pour {self.provider}. Réessayez dans quelques instants.",
            LLMErrorType.MODEL_NOT_FOUND: f"Le modèle demandé n'existe pas sur {self.provider}.",
            LLMErrorType.CONTEXT_LENGTH: "Le message est trop long pour ce modèle. Réduisez la taille de votre message.",
            LLMErrorType.CONTENT_FILTER: "Le contenu a été bloqué par le filtre de sécurité du fournisseur.",
            LLMErrorType.SERVER_ERROR: f"Erreur serveur chez {self.provider}. Réessayez plus tard.",
            LLMErrorType.TIMEOUT: f"Le serveur {self.provider} n'a pas répondu à temps.",
            LLMErrorType.INVALID_REQUEST: f"Requête invalide vers {self.provider}.",
            LLMErrorType.QUOTA_EXCEEDED: f"Quota dépassé pour {self.provider}. Vérifiez votre abonnement.",
            LLMErrorType.UNKNOWN: f"Erreur inattendue avec {self.provider}: {self.message}"
        }
        return messages.get(self.error_type, self.message)


def classify_openai_error(error: Exception, provider: str = "openai") -> LLMError:
    """
    Classifie une erreur OpenAI/compatible en LLMError.
    
    Args:
        error: L'exception OpenAI
        provider: Nom du fournisseur
        
    Returns:
        LLMError classifiée
    """
    error_str = str(error).lower()
    
    # Import dynamique pour éviter les erreurs si openai n'est pas installé
    try:
        from openai import (
            APIConnectionError,
            AuthenticationError,
            RateLimitError,
            NotFoundError,
            BadRequestError,
            APIStatusError
        )
        
        if isinstance(error, APIConnectionError):
            return LLMError(
                str(error), provider, LLMErrorType.CONNECTION_ERROR,
                original_error=error
            )
        elif isinstance(error, AuthenticationError):
            return LLMError(
                str(error), provider, LLMErrorType.AUTH_ERROR,
                http_status=401, original_error=error
            )
        elif isinstance(error, RateLimitError):
            return LLMError(
                str(error), provider, LLMErrorType.RATE_LIMIT,
                http_status=429, original_error=error
            )
        elif isinstance(error, NotFoundError):
            return LLMError(
                str(error), provider, LLMErrorType.MODEL_NOT_FOUND,
                http_status=404, original_error=error
            )
        elif isinstance(error, BadRequestError):
            if "context_length" in error_str or "token" in error_str:
                return LLMError(
                    str(error), provider, LLMErrorType.CONTEXT_LENGTH,
                    http_status=400, original_error=error
                )
            return LLMError(
                str(error), provider, LLMErrorType.INVALID_REQUEST,
                http_status=400, original_error=error
            )
        elif isinstance(error, APIStatusError):
            status = getattr(error, 'status_code', 500)
            if status >= 500:
                return LLMError(
                    str(error), provider, LLMErrorType.SERVER_ERROR,
                    http_status=status, original_error=error
                )
    except ImportError:
        pass
    
    # Fallback basé sur le texte de l'erreur
    if "timeout" in error_str:
        return LLMError(str(error), provider, LLMErrorType.TIMEOUT, original_error=error)
    elif "connect" in error_str or "connection" in error_str:
        return LLMError(str(error), provider, LLMErrorType.CONNECTION_ERROR, original_error=error)
    elif "auth" in error_str or "api key" in error_str or "unauthorized" in error_str:
        return LLMError(str(error), provider, LLMErrorType.AUTH_ERROR, original_error=error)
    elif "rate limit" in error_str or "too many" in error_str:
        return LLMError(str(error), provider, LLMErrorType.RATE_LIMIT, original_error=error)
    elif "not found" in error_str or "model" in error_str:
        return LLMError(str(error), provider, LLMErrorType.MODEL_NOT_FOUND, original_error=error)
    
    return LLMError(str(error), provider, LLMErrorType.UNKNOWN, original_error=error)


def classify_anthropic_error(error: Exception) -> LLMError:
    """Classifie une erreur Anthropic en LLMError."""
    error_str = str(error).lower()
    
    try:
        from anthropic import (
            APIConnectionError,
            AuthenticationError,
            RateLimitError,
            NotFoundError,
            BadRequestError
        )
        
        if isinstance(error, APIConnectionError):
            return LLMError(str(error), "anthropic", LLMErrorType.CONNECTION_ERROR, original_error=error)
        elif isinstance(error, AuthenticationError):
            return LLMError(str(error), "anthropic", LLMErrorType.AUTH_ERROR, http_status=401, original_error=error)
        elif isinstance(error, RateLimitError):
            return LLMError(str(error), "anthropic", LLMErrorType.RATE_LIMIT, http_status=429, original_error=error)
        elif isinstance(error, NotFoundError):
            return LLMError(str(error), "anthropic", LLMErrorType.MODEL_NOT_FOUND, http_status=404, original_error=error)
        elif isinstance(error, BadRequestError):
            if "context" in error_str or "token" in error_str:
                return LLMError(str(error), "anthropic", LLMErrorType.CONTEXT_LENGTH, http_status=400, original_error=error)
    except ImportError:
        pass
    
    return LLMError(str(error), "anthropic", LLMErrorType.UNKNOWN, original_error=error)


def classify_gemini_error(error: Exception) -> LLMError:
    """Classifie une erreur Google Gemini en LLMError."""
    error_str = str(error).lower()
    
    if "api key" in error_str or "invalid" in error_str:
        return LLMError(str(error), "gemini", LLMErrorType.AUTH_ERROR, original_error=error)
    elif "quota" in error_str or "rate" in error_str:
        return LLMError(str(error), "gemini", LLMErrorType.RATE_LIMIT, original_error=error)
    elif "safety" in error_str or "blocked" in error_str:
        return LLMError(str(error), "gemini", LLMErrorType.CONTENT_FILTER, original_error=error)
    elif "not found" in error_str or "model" in error_str:
        return LLMError(str(error), "gemini", LLMErrorType.MODEL_NOT_FOUND, original_error=error)
    
    return LLMError(str(error), "gemini", LLMErrorType.UNKNOWN, original_error=error)


def classify_http_error(status_code: int, message: str, provider: str) -> LLMError:
    """Classifie une erreur basée sur le code HTTP."""
    error_type = LLMErrorType.UNKNOWN
    
    if status_code == 401 or status_code == 403:
        error_type = LLMErrorType.AUTH_ERROR
    elif status_code == 404:
        error_type = LLMErrorType.MODEL_NOT_FOUND
    elif status_code == 429:
        error_type = LLMErrorType.RATE_LIMIT
    elif status_code == 400:
        error_type = LLMErrorType.INVALID_REQUEST
    elif status_code >= 500:
        error_type = LLMErrorType.SERVER_ERROR
    
    return LLMError(message, provider, error_type, http_status=status_code)
