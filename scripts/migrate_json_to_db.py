#!/usr/bin/env python3
"""
Script de migration one-shot : JSON → PostgreSQL

Migre les données existantes depuis les fichiers JSON vers PostgreSQL :
  - app/data/providers.json  →  table `providers`
  - app/data/text_tools_history.json  →  table `text_tool_history`

Usage :
  python scripts/migrate_json_to_db.py

Variables d'environnement requises :
  POSTGRES_URL  (ex: postgresql://user:pass@host:5432/nova)
"""

import json
import os
import sys
import uuid

# Ajouter le répertoire racine au path pour les imports Flask
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from app.extensions import db
from app.models.provider import Provider
from app.models.text_tool_history import TextToolHistory
from app.services.crypto_service import decrypt_api_key


def migrate_providers(app, data_dir: str) -> int:
    providers_path = os.path.join(data_dir, "providers.json")
    if not os.path.exists(providers_path):
        print(f"  [SKIP] {providers_path} introuvable")
        return 0

    with open(providers_path, encoding="utf-8") as f:
        data = json.load(f)

    providers_json = data.get("providers", [])
    active_id = data.get("active_provider_id")
    count = 0

    with app.app_context():
        for p in providers_json:
            pid = p.get("id") or str(uuid.uuid4())
            if Provider.query.get(pid):
                print(f"  [SKIP] Provider {p.get('name')} déjà en base")
                continue

            provider = Provider(
                id=pid,
                name=p.get("name", "Sans nom"),
                type=p.get("type", "ollama"),
                url=p.get("url", ""),
                api_key_encrypted=p.get("api_key_encrypted", ""),
                is_active=(pid == active_id),
            )
            provider.set_extra_headers(p.get("extra_headers", {}))
            db.session.add(provider)
            count += 1
            print(f"  [OK] Provider migré : {p.get('name')} ({p.get('type')})")

        db.session.commit()

    return count


def migrate_history(app, data_dir: str) -> int:
    history_path = os.path.join(data_dir, "text_tools_history.json")
    if not os.path.exists(history_path):
        print(f"  [SKIP] {history_path} introuvable")
        return 0

    with open(history_path, encoding="utf-8") as f:
        history = json.load(f)

    count = 0
    with app.app_context():
        for entry in history:
            hid = entry.get("id") or str(uuid.uuid4())
            if TextToolHistory.query.get(hid):
                continue

            record = TextToolHistory(
                id=hid,
                tool_type=entry.get("type", "unknown"),
                input_text=entry.get("input", ""),
                output_text=entry.get("output", ""),
                model_used=entry.get("model", ""),
            )
            record.set_options(entry.get("options", {}))
            db.session.add(record)
            count += 1

        db.session.commit()

    print(f"  [OK] {count} entrées d'historique migrées")
    return count


def main():
    app = create_app()

    with app.app_context():
        try:
            db.create_all()
            print("[OK] Tables créées / vérifiées")
        except Exception as e:
            print(f"[ERREUR] Impossible de créer les tables : {e}")
            sys.exit(1)

    data_dir = os.path.join(os.path.dirname(__file__), "..", "app", "data")
    print(f"\n=== Migration providers ({data_dir}/providers.json) ===")
    n = migrate_providers(app, data_dir)
    print(f"  → {n} providers migrés")

    print(f"\n=== Migration historique text tools ===")
    n = migrate_history(app, data_dir)
    print(f"  → {n} entrées d'historique migrées")

    print("\n✅ Migration terminée")


if __name__ == "__main__":
    main()
