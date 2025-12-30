"""
Classe de base abstraite pour les clients LLM.

Définit l'interface commune que tous les clients doivent implémenter.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Iterable


class BaseLLMClient(ABC):
    """Interface abstraite pour les clients LLM."""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Retourne le nom du fournisseur."""
        pass
    
    @abstractmethod
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Liste les modèles disponibles.
        
        Returns:
            Liste de dictionnaires avec au minimum:
            - name: Nom du modèle
            - id: Identifiant du modèle (peut être identique à name)
            - description: Description optionnelle
        """
        pass
    
    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Envoie une requête de chat non-streaming.
        
        Args:
            messages: Liste des messages [{role, content}]
            model: Nom du modèle à utiliser
            options: Options de génération (temperature, top_p, etc.)
            stream: Doit être False pour cette méthode
            
        Returns:
            Dictionnaire avec la réponse:
            - message: {role: "assistant", content: "..."}
            - usage: Optionnel, statistiques d'utilisation
        """
        pass
    
    @abstractmethod
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        images: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Iterable[Dict[str, Any]]:
        """
        Envoie une requête de chat streaming.
        
        Args:
            messages: Liste des messages [{role, content}]
            model: Nom du modèle à utiliser
            images: Liste optionnelle d'images en base64 (pour les modèles vision)
            options: Options de génération
            
        Yields:
            Dictionnaires avec les chunks de réponse:
            - message: {role: "assistant", content: "...", thinking: "..."}
            - done: bool indiquant si c'est le dernier chunk
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """
        Teste la connexion au fournisseur.
        
        Returns:
            Tuple (success: bool, message: str)
        """
        pass
    
    def supports_vision(self) -> bool:
        """
        Indique si le client supporte les images.
        
        Returns:
            True si les images sont supportées
        """
        return False
    
    def supports_streaming(self) -> bool:
        """
        Indique si le client supporte le streaming.
        
        Returns:
            True si le streaming est supporté
        """
        return True
    
    def get_default_model(self) -> Optional[str]:
        """
        Retourne le modèle par défaut pour ce provider.
        
        Returns:
            Nom du modèle par défaut ou None
        """
        return None
    
    def normalize_options(self, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Normalise les options pour ce provider.
        
        Chaque provider peut avoir des noms de paramètres différents.
        Cette méthode permet de convertir les options standard.
        
        Args:
            options: Options avec noms standards (temperature, top_p, etc.)
            
        Returns:
            Options converties pour le provider
        """
        if not options:
            return {}
        
        # Par défaut, retourne les options telles quelles
        # Les sous-classes peuvent override cette méthode
        return {
            k: v for k, v in options.items()
            if v is not None
        }
