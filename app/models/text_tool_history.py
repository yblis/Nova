import json
from datetime import datetime, timezone

from ..extensions import db


class TextToolHistory(db.Model):
    __tablename__ = "text_tool_history"

    id = db.Column(db.String(36), primary_key=True)
    tool_type = db.Column(db.String(64), nullable=False, index=True)
    input_text = db.Column(db.Text, nullable=True)
    output_text = db.Column(db.Text, nullable=True)
    model_used = db.Column(db.String(255), nullable=True)
    options = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def get_options(self) -> dict:
        if not self.options:
            return {}
        try:
            return json.loads(self.options)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_options(self, options: dict) -> None:
        self.options = json.dumps(options, ensure_ascii=False) if options else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.tool_type,
            "input": self.input_text or "",
            "output": self.output_text or "",
            "model": self.model_used or "",
            "options": self.get_options(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
