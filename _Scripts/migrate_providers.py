#!/usr/bin/env python3
"""
Script de migration des serveurs Ollama vers le nouveau format providers.

Ce script convertit les entrées de servers.json en providers.json,
permettant une transition transparente vers le système multi-fournisseurs.

Usage:
    python migrate_providers.py
    
    Ou automatiquement au démarrage de l'application via l'endpoint:
    POST /api/settings/providers/migrate
"""

import json
import os
import sys
import time
from pathlib import Path


def migrate(data_dir: str = None) -> dict:
    """
    Migre servers.json vers providers.json.
    
    Args:
        data_dir: Répertoire contenant les fichiers de données
        
    Returns:
        dict avec le résultat de la migration
    """
    if data_dir is None:
        # Déterminer le répertoire data
        script_dir = Path(__file__).parent
        data_dir = script_dir.parent / "app" / "data"
    else:
        data_dir = Path(data_dir)
    
    servers_path = data_dir / "servers.json"
    providers_path = data_dir / "providers.json"
    
    result = {
        "success": False,
        "migrated_count": 0,
        "message": ""
    }
    
    # Vérifier si providers.json existe déjà avec des données
    if providers_path.exists():
        try:
            with open(providers_path, 'r', encoding='utf-8') as f:
                providers_data = json.load(f)
                if providers_data.get("providers"):
                    result["message"] = "providers.json existe déjà avec des fournisseurs configurés"
                    result["success"] = True
                    return result
        except (json.JSONDecodeError, KeyError):
            pass
    
    # Vérifier si servers.json existe
    if not servers_path.exists():
        result["message"] = "Aucun fichier servers.json trouvé"
        result["success"] = True
        return result
    
    # Charger les serveurs
    try:
        with open(servers_path, 'r', encoding='utf-8') as f:
            servers_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        result["message"] = f"Erreur lors de la lecture de servers.json: {e}"
        return result
    
    servers = servers_data.get("servers", [])
    if not servers:
        result["message"] = "Aucun serveur à migrer"
        result["success"] = True
        return result
    
    # Créer la structure providers
    timestamp = int(time.time())
    
    providers = []
    active_id = None
    
    for server in servers:
        provider = {
            "id": server["id"],
            "name": server["name"],
            "type": "ollama",
            "url": server["url"],
            "api_key_encrypted": "",
            "extra_headers": {},
            "created_at": timestamp,
            "updated_at": timestamp
        }
        providers.append(provider)
        
        # Conserver le serveur actif
        if server["id"] == servers_data.get("active_server_id"):
            active_id = server["id"]
    
    # Si pas d'actif défini, prendre le premier
    if not active_id and providers:
        active_id = providers[0]["id"]
    
    new_data = {
        "active_provider_id": active_id,
        "providers": providers
    }
    
    # Sauvegarder
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        with open(providers_path, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        result["message"] = f"Erreur lors de l'écriture de providers.json: {e}"
        return result
    
    result["success"] = True
    result["migrated_count"] = len(providers)
    result["message"] = f"{len(providers)} serveur(s) Ollama migré(s) vers providers.json"
    
    print(f"✅ Migration réussie: {result['message']}")
    
    return result


def main():
    """Point d'entrée CLI."""
    print("🔄 Migration des serveurs Ollama vers providers...")
    print()
    
    result = migrate()
    
    if result["success"]:
        print(f"✅ {result['message']}")
        sys.exit(0)
    else:
        print(f"❌ {result['message']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
