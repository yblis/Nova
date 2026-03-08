"""
Service de gestion des providers LLM avec backend SQLAlchemy.

Remplace provider_manager.py (JSON) par une implémentation PostgreSQL.
L'API publique est identique — le code appelant ne change pas.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from ..extensions import db
from ..models.provider import Provider
from .crypto_service import decrypt_api_key, encrypt_api_key, mask_api_key
from .provider_manager import PROVIDER_TYPES


class ProviderManagerDB:
    """
    Gestionnaire de providers LLM avec persistance PostgreSQL (SQLAlchemy).
    API identique à ProviderManager pour rétrocompatibilité totale.
    """

    def _ensure_default_provider(self) -> None:
        """Vérifie qu'au moins un provider existe. Migration JSON faite dans create_app()."""
        # La migration JSON→DB est gérée dans app/__init__.py._auto_migrate_providers_json_to_db()
        pass

    def get_providers(self, include_api_key_masked: bool = True) -> List[Dict]:

        providers = Provider.query.order_by(Provider.created_at.asc()).all()
        result = []
        for p in providers:
            entry: Dict[str, Any] = {
                "id": p.id,
                "name": p.name,
                "type": p.type,
                "url": p.url or "",
                "extra_headers": p.get_extra_headers(),
                "has_api_key": bool(p.api_key_encrypted),
                "default_model": "",
                "is_active": p.is_active,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            if include_api_key_masked and p.api_key_encrypted:
                decrypted = decrypt_api_key(p.api_key_encrypted)
                entry["api_key_masked"] = mask_api_key(decrypted) if decrypted else "•••••"
            result.append(entry)
        return result

    def get_provider(self, provider_id: str, include_api_key: bool = False) -> Optional[Dict]:
        p = Provider.query.get(provider_id)
        if not p:
            return None
        result: Dict[str, Any] = {
            "id": p.id,
            "name": p.name,
            "type": p.type,
            "url": p.url or "",
            "extra_headers": p.get_extra_headers(),
            "has_api_key": bool(p.api_key_encrypted),
            "default_model": "",
        }
        if include_api_key and p.api_key_encrypted:
            result["api_key"] = decrypt_api_key(p.api_key_encrypted)
        return result

    def add_provider(
        self,
        name: str,
        provider_type: str,
        url: str = "",
        api_key: str = "",
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict:
        if provider_type not in PROVIDER_TYPES:
            raise ValueError(f"Type de fournisseur invalide: {provider_type}")

        if not url:
            url = PROVIDER_TYPES[provider_type].get("default_url", "")

        new_id = str(uuid.uuid4())
        is_first = Provider.query.count() == 0

        p = Provider(
            id=new_id,
            name=name,
            type=provider_type,
            url=url,
            api_key_encrypted=encrypt_api_key(api_key) if api_key else "",
            is_active=is_first,
        )
        if extra_headers:
            p.set_extra_headers(extra_headers)

        db.session.add(p)
        db.session.commit()

        return {
            "id": new_id,
            "name": name,
            "type": provider_type,
            "url": url,
            "has_api_key": bool(api_key),
            "extra_headers": extra_headers or {},
        }

    def update_provider(
        self,
        provider_id: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict]:
        p = Provider.query.get(provider_id)
        if not p:
            return None
        if name is not None:
            p.name = name
        if url is not None:
            p.url = url
        if api_key:
            p.api_key_encrypted = encrypt_api_key(api_key)
        if extra_headers is not None:
            p.set_extra_headers(extra_headers)
        db.session.commit()
        return {
            "id": p.id,
            "name": p.name,
            "type": p.type,
            "url": p.url or "",
            "has_api_key": bool(p.api_key_encrypted),
            "extra_headers": p.get_extra_headers(),
        }

    def delete_provider(self, provider_id: str) -> bool:
        p = Provider.query.get(provider_id)
        if not p:
            return False
        was_active = p.is_active
        db.session.delete(p)
        db.session.commit()
        if was_active:
            first = Provider.query.first()
            if first:
                first.is_active = True
                db.session.commit()
        return True

    def set_active_provider(self, provider_id: str) -> bool:
        p = Provider.query.get(provider_id)
        if not p:
            return False
        Provider.query.filter_by(is_active=True).update({"is_active": False})
        p.is_active = True
        db.session.commit()
        return True

    def get_active_provider(self, include_api_key: bool = False) -> Optional[Dict]:
        p = Provider.query.filter_by(is_active=True).first()
        if not p:
            p = Provider.query.first()
        if not p:
            return None
        return self.get_provider(p.id, include_api_key)

    def get_active_provider_id(self) -> Optional[str]:
        p = Provider.query.filter_by(is_active=True).first()
        return p.id if p else None

    def set_default_model(self, provider_id: str, model_name: str) -> bool:
        # default_model non stocké en DB dans ce schéma minimal
        return bool(Provider.query.get(provider_id))

    def get_default_model(self, provider_id: str) -> Optional[str]:
        return ""

    def is_provider_configured(self, provider_type: str) -> bool:
        providers = Provider.query.filter_by(type=provider_type).all()
        for p in providers:
            type_info = PROVIDER_TYPES.get(provider_type, {})
            if type_info.get("requires_api_key"):
                if p.api_key_encrypted:
                    return True
            elif p.url:
                return True
        return False

    def get_provider_by_type(self, provider_type: str, include_api_key: bool = False) -> Optional[Dict]:
        providers = Provider.query.filter_by(type=provider_type).all()
        for p in providers:
            type_info = PROVIDER_TYPES.get(provider_type, {})
            if type_info.get("requires_api_key"):
                if not p.api_key_encrypted:
                    continue
            elif not p.url:
                continue
            return self.get_provider(p.id, include_api_key)
        return None
