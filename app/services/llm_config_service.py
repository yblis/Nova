"""
Service de configuration LLM par défaut.

Ce service permet de gérer les paramètres de génération LLM par défaut
(system prompt, temperature, top_p, etc.) qui s'appliquent aux nouvelles conversations.
"""

import json
import os
from typing import Dict, Any, Optional
from flask import current_app


# Valeurs par défaut
DEFAULT_CONFIG = {
    "default_system_prompt": "",
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "repeat_penalty": 1.1,
    "num_ctx": 4096,
    "auto_generate_title": True
}


def _get_config_path() -> str:
    """Retourne le chemin du fichier de configuration."""
    try:
        return os.path.join(current_app.root_path, "data", "llm_config.json")
    except RuntimeError:
        # Hors contexte Flask
        return os.path.join(os.path.dirname(__file__), "..", "data", "llm_config.json")


def _load_config() -> Dict[str, Any]:
    """Charge la configuration depuis le fichier JSON."""
    config_path = _get_config_path()
    
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # Merge avec les valeurs par défaut
                return {**DEFAULT_CONFIG, **loaded}
    except Exception:
        pass
    
    return DEFAULT_CONFIG.copy()


def _save_config(config: Dict[str, Any]) -> bool:
    """Sauvegarde la configuration dans le fichier JSON."""
    config_path = _get_config_path()
    
    try:
        # Créer le répertoire si nécessaire
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        try:
            current_app.logger.error(f"Failed to save LLM config: {e}")
        except RuntimeError:
            pass
        return False


def get_config() -> Dict[str, Any]:
    """
    Récupère la configuration complète.
    
    Returns:
        Dictionnaire avec la configuration LLM.
    """
    return _load_config()


def set_config(updates: Dict[str, Any]) -> bool:
    """
    Met à jour la configuration.
    
    Args:
        updates: Dictionnaire avec les valeurs à mettre à jour.
    
    Returns:
        True si la sauvegarde a réussi.
    """
    config = _load_config()
    
    # Valider les valeurs numériques
    if "temperature" in updates:
        temp = float(updates["temperature"])
        if 0 <= temp <= 2:
            config["temperature"] = temp
    
    if "top_p" in updates:
        top_p = float(updates["top_p"])
        if 0 <= top_p <= 1:
            config["top_p"] = top_p
    
    if "top_k" in updates:
        top_k = int(updates["top_k"])
        if 1 <= top_k <= 100:
            config["top_k"] = top_k
    
    if "repeat_penalty" in updates:
        rp = float(updates["repeat_penalty"])
        if 1 <= rp <= 2:
            config["repeat_penalty"] = rp
    
    if "num_ctx" in updates:
        num_ctx = int(updates["num_ctx"])
        if 2048 <= num_ctx <= 128000:
            config["num_ctx"] = num_ctx
    
    if "default_system_prompt" in updates:
        config["default_system_prompt"] = str(updates["default_system_prompt"])
    
    if "auto_generate_title" in updates:
        config["auto_generate_title"] = bool(updates["auto_generate_title"])
    
    return _save_config(config)


def get_default_system_prompt() -> str:
    """
    Récupère le system prompt par défaut.
    
    Returns:
        Le system prompt par défaut ou une chaîne vide.
    """
    config = _load_config()
    return config.get("default_system_prompt", "")


def get_default_options() -> Dict[str, Any]:
    """
    Récupère les options de génération par défaut.
    
    Returns:
        Dictionnaire avec les options (temperature, top_p, top_k, repeat_penalty, num_ctx).
    """
    config = _load_config()
    return {
        "temperature": config.get("temperature", DEFAULT_CONFIG["temperature"]),
        "top_p": config.get("top_p", DEFAULT_CONFIG["top_p"]),
        "top_k": config.get("top_k", DEFAULT_CONFIG["top_k"]),
        "repeat_penalty": config.get("repeat_penalty", DEFAULT_CONFIG["repeat_penalty"]),
        "num_ctx": config.get("num_ctx", DEFAULT_CONFIG["num_ctx"])
    }


def is_auto_title_enabled() -> bool:
    """
    Vérifie si la génération automatique de titre est activée.
    
    Returns:
        True si la génération automatique est activée, False sinon.
    """
    config = _load_config()
    return config.get("auto_generate_title", True)
