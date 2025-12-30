"""
Service de chiffrement pour les clés API des fournisseurs LLM.

Utilise Fernet (cryptography) pour un chiffrement symétrique sécurisé.
La clé de chiffrement est stockée dans les variables d'environnement.
"""

import os
import base64
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _get_or_create_key() -> bytes:
    """
    Récupère la clé de chiffrement depuis l'environnement ou en génère une nouvelle.
    
    Returns:
        La clé Fernet en bytes
    """
    key = os.environ.get("LLM_ENCRYPTION_KEY", "")
    
    if not key:
        # Générer une nouvelle clé
        key = Fernet.generate_key().decode('utf-8')
        # Log un avertissement car la clé devrait être persistée
        try:
            current_app.logger.warning(
                "LLM_ENCRYPTION_KEY not set in environment. "
                f"Generated new key: {key} - Add this to your .env file!"
            )
        except RuntimeError:
            # Hors contexte Flask
            print(f"WARNING: Generated new LLM_ENCRYPTION_KEY={key}")
            print("Add this to your .env file to persist API keys encryption!")
        
        # Stocker temporairement dans l'environnement pour cette session
        os.environ["LLM_ENCRYPTION_KEY"] = key
    
    return key.encode('utf-8')


def _get_fernet() -> Fernet:
    """Retourne une instance Fernet avec la clé courante."""
    key = _get_or_create_key()
    return Fernet(key)


def encrypt_api_key(api_key: str) -> str:
    """
    Chiffre une clé API.
    
    Args:
        api_key: La clé API en clair
        
    Returns:
        La clé API chiffrée en base64
    """
    if not api_key:
        return ""
    
    fernet = _get_fernet()
    encrypted = fernet.encrypt(api_key.encode('utf-8'))
    return base64.urlsafe_b64encode(encrypted).decode('utf-8')


def decrypt_api_key(encrypted_key: str) -> Optional[str]:
    """
    Déchiffre une clé API.
    
    Args:
        encrypted_key: La clé API chiffrée en base64
        
    Returns:
        La clé API en clair, ou None si le déchiffrement échoue
    """
    if not encrypted_key:
        return None
    
    try:
        fernet = _get_fernet()
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode('utf-8'))
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode('utf-8')
    except (InvalidToken, ValueError, Exception) as e:
        try:
            current_app.logger.error(f"Failed to decrypt API key: {e}")
        except RuntimeError:
            pass
        return None


def mask_api_key(api_key: str, visible_chars: int = 4) -> str:
    """
    Masque une clé API pour affichage sécurisé.
    
    Args:
        api_key: La clé API en clair
        visible_chars: Nombre de caractères à afficher à la fin
        
    Returns:
        La clé masquée (ex: "•••••••••abc123")
    """
    if not api_key:
        return ""
    
    if len(api_key) <= visible_chars:
        return "•" * len(api_key)
    
    return "•" * (len(api_key) - visible_chars) + api_key[-visible_chars:]


def is_key_valid(encrypted_key: str) -> bool:
    """
    Vérifie si une clé chiffrée peut être déchiffrée.
    
    Args:
        encrypted_key: La clé API chiffrée
        
    Returns:
        True si la clé est valide et peut être déchiffrée
    """
    return decrypt_api_key(encrypted_key) is not None
