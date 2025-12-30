"""
Service de configuration Audio (STT/TTS).

Ce service permet de gérer les paramètres globaux pour les services audio :
- Provider et Modèle STT (Speech-to-Text)
- Provider, Modèle et Voix TTS (Text-to-Speech)
"""

import json
import os
from typing import Dict, Any, Optional
from flask import current_app


# Valeurs par défaut
DEFAULT_CONFIG = {
    # STT Settings
    "stt_enabled": True,
    "stt_provider_id": "",  # Empty = browser native
    "stt_model": "",
    
    # TTS Settings
    "tts_enabled": True,
    "tts_provider_id": "",  # Empty = browser native
    "tts_model": "",
    "tts_voice": "",
    "tts_speed": 1.0,
    "play_start_sound": False
}


class AudioConfigService:
    def _get_config_path(self) -> str:
        """Retourne le chemin du fichier de configuration."""
        try:
            return os.path.join(current_app.root_path, "data", "audio_config.json")
        except RuntimeError:
            # Hors contexte Flask
            return os.path.join(os.path.dirname(__file__), "..", "data", "audio_config.json")

    def _load_config(self) -> Dict[str, Any]:
        """Charge la configuration depuis le fichier JSON."""
        config_path = self._get_config_path()
        
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Merge avec les valeurs par défaut pour garantir que toutes les clés existent
                    return {**DEFAULT_CONFIG, **loaded}
        except Exception:
            pass
        
        return DEFAULT_CONFIG.copy()

    def _save_config(self, config: Dict[str, Any]) -> bool:
        """Sauvegarde la configuration dans le fichier JSON."""
        config_path = self._get_config_path()
        
        try:
            # Créer le répertoire si nécessaire
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            try:
                current_app.logger.error(f"Failed to save Audio config: {e}")
            except RuntimeError:
                pass
            return False

    def get_config(self) -> Dict[str, Any]:
        """
        Récupère la configuration audio complète.
        
        Returns:
            Dictionnaire avec la configuration.
        """
        return self._load_config()

    def set_config(self, updates: Dict[str, Any]) -> bool:
        """
        Met à jour la configuration audio.
        
        Args:
            updates: Dictionnaire avec les valeurs à mettre à jour.
        
        Returns:
            True si la sauvegarde a réussi.
        """
        config = self._load_config()
        
        # Mettre à jour les champs autorisés
        allowed_keys = DEFAULT_CONFIG.keys()
        boolean_keys = {'stt_enabled', 'tts_enabled', 'play_start_sound'}
        
        for key, value in updates.items():
            if key in allowed_keys:
                if key == "tts_speed":
                    try:
                        speed = float(value)
                        if 0.25 <= speed <= 4.0:
                            config[key] = speed
                    except (ValueError, TypeError):
                        pass
                elif key in boolean_keys:
                    # Handle boolean conversion from various sources (JS true/false, strings, etc.)
                    if isinstance(value, bool):
                        config[key] = value
                    elif isinstance(value, str):
                        config[key] = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        config[key] = bool(value)
                else:
                    config[key] = str(value) if value is not None else ""
        
        return self._save_config(config)

# Singleton instance
audio_config_service = AudioConfigService()

# For backward compatibility or direct function usage if needed, though mostly used via instance now
def get_config():
    return audio_config_service.get_config()

def set_config(updates):
    return audio_config_service.set_config(updates)
