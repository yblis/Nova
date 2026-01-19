"""
Service de configuration Audio (STT/TTS).

Ce service permet de gérer les paramètres globaux pour les services audio :
- Provider et Modèle STT (Speech-to-Text)
- Provider, Modèle et Voix TTS (Text-to-Speech)

Quand TTS ou STT est désactivé, le container Docker correspondant est arrêté
pour libérer les ressources GPU.
"""

import json
import os
import subprocess
import logging
from typing import Dict, Any, Optional
from flask import current_app

logger = logging.getLogger(__name__)

# Noms des containers Docker pour TTS et STT
TTS_CONTAINER_NAME = "nova-alltalk"
STT_CONTAINER_NAME = "nova-whisper"


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

    def _manage_docker_container(self, container_name: str, action: str) -> bool:
        """
        Démarre ou arrête un container Docker.
        
        Args:
            container_name: Nom du container (ex: nova-alltalk)
            action: "start" ou "stop"
            
        Returns:
            True si l'action a réussi
        """
        try:
            result = subprocess.run(
                ["docker", action, container_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.info(f"Container {container_name} {action}ed successfully")
                return True
            else:
                logger.error(f"Failed to {action} container {container_name}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while trying to {action} container {container_name}")
            return False
        except FileNotFoundError:
            logger.error("Docker command not found")
            return False
        except Exception as e:
            logger.error(f"Error managing container {container_name}: {e}")
            return False

    def _is_container_running(self, container_name: str) -> bool:
        """Vérifie si un container Docker est en cours d'exécution."""
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except Exception:
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
        Gère également le démarrage/arrêt des containers Docker TTS et STT
        quand leur état enabled change.
        
        Args:
            updates: Dictionnaire avec les valeurs à mettre à jour.
        
        Returns:
            True si la sauvegarde a réussi.
        """
        # Charger la config actuelle pour détecter les changements
        old_config = self._load_config()
        config = old_config.copy()
        
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
        
        # Sauvegarder la config
        save_success = self._save_config(config)
        
        # Gérer les containers Docker si les états enabled ont changé
        if save_success:
            # TTS (AllTalk)
            old_tts_enabled = old_config.get('tts_enabled', True)
            new_tts_enabled = config.get('tts_enabled', True)
            
            if old_tts_enabled and not new_tts_enabled:
                # TTS désactivé -> arrêter le container
                logger.info("TTS disabled, stopping nova-alltalk container...")
                self._manage_docker_container(TTS_CONTAINER_NAME, "stop")
            elif not old_tts_enabled and new_tts_enabled:
                # TTS activé -> démarrer le container
                logger.info("TTS enabled, starting nova-alltalk container...")
                self._manage_docker_container(TTS_CONTAINER_NAME, "start")
            
            # STT (Whisper)
            old_stt_enabled = old_config.get('stt_enabled', True)
            new_stt_enabled = config.get('stt_enabled', True)
            
            if old_stt_enabled and not new_stt_enabled:
                # STT désactivé -> arrêter le container
                logger.info("STT disabled, stopping nova-whisper container...")
                self._manage_docker_container(STT_CONTAINER_NAME, "stop")
            elif not old_stt_enabled and new_stt_enabled:
                # STT activé -> démarrer le container
                logger.info("STT enabled, starting nova-whisper container...")
                self._manage_docker_container(STT_CONTAINER_NAME, "start")
        
        return save_success

    def sync_containers(self) -> Dict[str, Any]:
        """
        Synchronise l'état des containers Docker avec la configuration actuelle.
        Arrête les containers dont le service est désactivé, démarre ceux qui sont activés.
        
        Returns:
            Dict avec le résultat de la synchronisation pour chaque service.
        """
        config = self._load_config()
        results = {}
        
        # TTS (AllTalk)
        tts_enabled = config.get('tts_enabled', True)
        tts_running = self._is_container_running(TTS_CONTAINER_NAME)
        
        if tts_enabled and not tts_running:
            logger.info("TTS is enabled but container is stopped, starting...")
            results['tts'] = {
                'action': 'start',
                'success': self._manage_docker_container(TTS_CONTAINER_NAME, "start")
            }
        elif not tts_enabled and tts_running:
            logger.info("TTS is disabled but container is running, stopping...")
            results['tts'] = {
                'action': 'stop',
                'success': self._manage_docker_container(TTS_CONTAINER_NAME, "stop")
            }
        else:
            results['tts'] = {
                'action': 'none',
                'success': True,
                'message': f"Already {'running' if tts_running else 'stopped'}"
            }
        
        # STT (Whisper)
        stt_enabled = config.get('stt_enabled', True)
        stt_running = self._is_container_running(STT_CONTAINER_NAME)
        
        if stt_enabled and not stt_running:
            logger.info("STT is enabled but container is stopped, starting...")
            results['stt'] = {
                'action': 'start',
                'success': self._manage_docker_container(STT_CONTAINER_NAME, "start")
            }
        elif not stt_enabled and stt_running:
            logger.info("STT is disabled but container is running, stopping...")
            results['stt'] = {
                'action': 'stop',
                'success': self._manage_docker_container(STT_CONTAINER_NAME, "stop")
            }
        else:
            results['stt'] = {
                'action': 'none',
                'success': True,
                'message': f"Already {'running' if stt_running else 'stopped'}"
            }
        
        return results

# Singleton instance
audio_config_service = AudioConfigService()

# For backward compatibility or direct function usage if needed, though mostly used via instance now
def get_config():
    return audio_config_service.get_config()

def set_config(updates):
    return audio_config_service.set_config(updates)

def sync_audio_containers():
    """Synchronise les containers audio avec la configuration actuelle."""
    return audio_config_service.sync_containers()
