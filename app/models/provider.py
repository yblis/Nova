import json
from datetime import datetime, timezone

from ..extensions import db


class Provider(db.Model):
    __tablename__ = "providers"

    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(64), nullable=False)
    url = db.Column(db.String(1024), nullable=True)
    api_key_encrypted = db.Column(db.Text, nullable=True, default="")
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    extra_headers = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def get_extra_headers(self) -> dict:
        if not self.extra_headers:
            return {}
        try:
            return json.loads(self.extra_headers)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_extra_headers(self, headers: dict) -> None:
        self.extra_headers = json.dumps(headers) if headers else None

    def to_dict(self, include_api_key: bool = False) -> dict:
        result = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "url": self.url or "",
            "is_active": self.is_active,
            "extra_headers": self.get_extra_headers(),
            "api_key_encrypted": self.api_key_encrypted or "",
        }
        if include_api_key and self.api_key_encrypted:
            from ..services.crypto_service import decrypt_api_key
            result["api_key"] = decrypt_api_key(self.api_key_encrypted) or ""
        return result
