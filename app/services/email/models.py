from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any


@dataclass
class EmailEnvelope:
    uid: str
    subject: str
    sender: str
    sender_email: str
    to: str
    date: str
    flags: List[str] = field(default_factory=list)
    is_read: bool = False
    is_flagged: bool = False
    has_attachments: bool = False
    size: int = 0
    folder: str = "INBOX"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EmailMessage:
    uid: str
    subject: str
    sender: str
    sender_email: str
    to: str
    cc: str
    date: str
    body_text: str
    body_html: str
    flags: List[str] = field(default_factory=list)
    is_read: bool = False
    is_flagged: bool = False
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    in_reply_to: str = ""
    message_id: str = ""
    references: str = ""
    folder: str = "INBOX"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EmailFolder:
    name: str
    delimiter: str = "/"
    flags: List[str] = field(default_factory=list)
    total: int = 0
    unread: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
