import re
import email as email_lib
import email.header
import email.utils
from typing import List, Dict, Any, Tuple


def _decode_header(header_value: str) -> str:
    if not header_value:
        return ""
    decoded_parts = email_lib.header.decode_header(header_value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result).strip()


def _parse_email_address(addr_str: str) -> Tuple[str, str]:
    if not addr_str:
        return ("", "")
    decoded = _decode_header(addr_str)
    name, addr = email_lib.utils.parseaddr(decoded)
    return (name or addr, addr)


def _extract_body(msg: email_lib.message.Message) -> Tuple[str, str]:
    body_text = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
            except Exception:
                continue

            if content_type == "text/plain" and not body_text:
                body_text = text
            elif content_type == "text/html" and not body_html:
                body_html = text
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    body_html = text
                else:
                    body_text = text
        except Exception:
            pass

    return body_text, body_html


def _extract_attachments_info(msg: email_lib.message.Message) -> List[Dict[str, Any]]:
    attachments = []
    if not msg.is_multipart():
        return attachments

    for part in msg.walk():
        disposition = str(part.get("Content-Disposition", ""))
        if "attachment" in disposition or (
            part.get_content_maintype() not in ("text", "multipart")
            and "inline" not in disposition
        ):
            filename = part.get_filename()
            if filename:
                filename = _decode_header(filename)
                payload = part.get_payload(decode=True)
                attachments.append({
                    "filename": filename,
                    "content_type": part.get_content_type(),
                    "size": len(payload) if payload else 0,
                })

    return attachments


def _parse_flags(flag_str: str) -> Tuple[List[str], bool, bool]:
    flags = []
    if isinstance(flag_str, bytes):
        flag_str = flag_str.decode("utf-8", errors="replace")

    raw_flags = re.findall(r'\\?\w+', flag_str)
    is_read = "\\Seen" in raw_flags
    is_flagged = "\\Flagged" in raw_flags
    flags = raw_flags
    return flags, is_read, is_flagged
