import re
import email as email_lib
import email.mime.text
import email.mime.multipart
import email.mime.base
import email.utils
from typing import List, Optional, Dict, Any

from flask import current_app

from .models import EmailEnvelope, EmailMessage, EmailFolder
from .config import _load_config
from .connection import _get_imap_connection, _get_pop3_connection, _get_smtp_connection
from .parser import _decode_header, _parse_email_address, _extract_body, _extract_attachments_info, _parse_flags


def is_email_available() -> bool:
    config = _load_config()
    protocol = config.get("reception_protocol", "imap")

    if protocol == "pop3":
        if not config.get("pop3_host") or not config.get("email_address"):
            return False
    else:
        if not config.get("imap_host") or not config.get("email_address"):
            return False

    if not config.get("password_encrypted"):
        return False

    try:
        if protocol == "pop3":
            pop3 = _get_pop3_connection()
            pop3.quit()
        else:
            imap = _get_imap_connection()
            imap.logout()
        return True
    except Exception:
        return False


def list_folders() -> List[EmailFolder]:
    imap = _get_imap_connection()
    try:
        status, folder_list = imap.list()
        if status != "OK":
            return []

        folders = []
        for item in folder_list:
            if isinstance(item, bytes):
                item = item.decode("utf-8", errors="replace")

            match = re.match(r'\(([^)]*)\)\s+"([^"]+)"\s+"?([^"]+)"?', str(item))
            if match:
                flags_str, delimiter, name = match.groups()
                flags = [f.strip() for f in flags_str.split() if f.strip()]

                if "\\Noselect" in flags:
                    continue

                folder = EmailFolder(
                    name=name.strip('"'),
                    delimiter=delimiter,
                    flags=flags,
                )

                try:
                    stat_status, stat_data = imap.status(
                        f'"{folder.name}"',
                        "(MESSAGES UNSEEN)"
                    )
                    if stat_status == "OK" and stat_data[0]:
                        stat_str = stat_data[0]
                        if isinstance(stat_str, bytes):
                            stat_str = stat_str.decode("utf-8", errors="replace")
                        msg_match = re.search(r'MESSAGES\s+(\d+)', stat_str)
                        unseen_match = re.search(r'UNSEEN\s+(\d+)', stat_str)
                        if msg_match:
                            folder.total = int(msg_match.group(1))
                        if unseen_match:
                            folder.unread = int(unseen_match.group(1))
                except Exception:
                    pass

                folders.append(folder)

        return folders
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def list_emails(
    folder: str = None,
    max_results: int = None,
    unread_only: bool = False,
) -> List[EmailEnvelope]:
    config = _load_config()
    if config.get("reception_protocol") == "pop3":
        return _pop3_list_emails(max_results=max_results)
    return _imap_list_emails(folder=folder, max_results=max_results, unread_only=unread_only)


def _imap_list_emails(
    folder: str = None,
    max_results: int = None,
    unread_only: bool = False,
) -> List[EmailEnvelope]:
    config = _load_config()
    folder = folder or config.get("default_folder", "INBOX")
    max_results = max_results or config.get("max_emails", 10)

    imap = _get_imap_connection()
    try:
        status, _ = imap.select(f'"{folder}"', readonly=True)
        if status != "OK":
            raise ValueError(f"Impossible d'ouvrir le dossier: {folder}")

        search_criteria = "UNSEEN" if unread_only else "ALL"
        status, data = imap.search(None, search_criteria)
        if status != "OK":
            return []

        uid_list = data[0].split()
        if not uid_list:
            return []

        uid_list = uid_list[-max_results:]
        uid_list.reverse()

        envelopes = []
        for uid_bytes in uid_list:
            uid = uid_bytes.decode("utf-8")
            try:
                status, msg_data = imap.fetch(
                    uid_bytes,
                    "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE CONTENT-TYPE)])"
                )
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw_flags = ""
                raw_header = b""
                for part in msg_data:
                    if isinstance(part, tuple):
                        if isinstance(part[0], bytes) and b"FLAGS" in part[0]:
                            raw_flags = part[0].decode("utf-8", errors="replace")
                        raw_header = part[1] if len(part) > 1 else b""
                    elif isinstance(part, bytes) and b"FLAGS" in part:
                        raw_flags = part.decode("utf-8", errors="replace")

                msg = email_lib.message_from_bytes(raw_header)
                subject = _decode_header(msg.get("Subject", ""))
                sender_name, sender_email = _parse_email_address(msg.get("From", ""))
                to = _decode_header(msg.get("To", ""))
                date_str = msg.get("Date", "")

                flags, is_read, is_flagged = _parse_flags(raw_flags)

                content_type = msg.get("Content-Type", "")
                has_attachments = "multipart/mixed" in content_type.lower()

                envelopes.append(EmailEnvelope(
                    uid=uid,
                    subject=subject or "(Sans sujet)",
                    sender=sender_name,
                    sender_email=sender_email,
                    to=to,
                    date=date_str,
                    flags=flags,
                    is_read=is_read,
                    is_flagged=is_flagged,
                    has_attachments=has_attachments,
                    folder=folder,
                ))
            except Exception as e:
                try:
                    current_app.logger.warning(f"Error parsing email UID {uid}: {e}")
                except RuntimeError:
                    pass
                continue

        return envelopes
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def _pop3_list_emails(max_results: int = None) -> List[EmailEnvelope]:
    config = _load_config()
    max_results = max_results or config.get("max_emails", 10)

    pop3 = _get_pop3_connection()
    try:
        num_messages, _ = pop3.stat()
        if num_messages == 0:
            return []

        start = max(1, num_messages - max_results + 1)
        envelopes = []

        for msg_num in range(num_messages, start - 1, -1):
            try:
                response, header_lines, _ = pop3.top(msg_num, 0)
                raw_header = b"\r\n".join(header_lines)
                msg = email_lib.message_from_bytes(raw_header)

                subject = _decode_header(msg.get("Subject", ""))
                sender_name, sender_email = _parse_email_address(msg.get("From", ""))
                to = _decode_header(msg.get("To", ""))
                date_str = msg.get("Date", "")
                content_type = msg.get("Content-Type", "")
                has_attachments = "multipart/mixed" in content_type.lower()

                envelopes.append(EmailEnvelope(
                    uid=str(msg_num),
                    subject=subject or "(Sans sujet)",
                    sender=sender_name,
                    sender_email=sender_email,
                    to=to,
                    date=date_str,
                    flags=[],
                    is_read=False,
                    is_flagged=False,
                    has_attachments=has_attachments,
                    folder="INBOX",
                ))
            except Exception as e:
                try:
                    current_app.logger.warning(f"Error parsing POP3 email {msg_num}: {e}")
                except RuntimeError:
                    pass
                continue

        return envelopes
    finally:
        try:
            pop3.quit()
        except Exception:
            pass


def read_email(uid: str, folder: str = None) -> Optional[EmailMessage]:
    config = _load_config()
    if config.get("reception_protocol") == "pop3":
        return _pop3_read_email(uid)
    return _imap_read_email(uid, folder)


def _pop3_read_email(uid: str) -> Optional[EmailMessage]:
    pop3 = _get_pop3_connection()
    try:
        msg_num = int(uid)
        response, lines, _ = pop3.retr(msg_num)
        raw_email = b"\r\n".join(lines)
        msg = email_lib.message_from_bytes(raw_email)

        subject = _decode_header(msg.get("Subject", ""))
        sender_name, sender_email = _parse_email_address(msg.get("From", ""))
        to = _decode_header(msg.get("To", ""))
        cc = _decode_header(msg.get("Cc", ""))
        date_str = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")
        in_reply_to = msg.get("In-Reply-To", "")
        references = msg.get("References", "")

        body_text, body_html = _extract_body(msg)
        attachments = _extract_attachments_info(msg)

        return EmailMessage(
            uid=uid,
            subject=subject or "(Sans sujet)",
            sender=sender_name,
            sender_email=sender_email,
            to=to,
            cc=cc,
            date=date_str,
            body_text=body_text,
            body_html=body_html,
            flags=[],
            is_read=False,
            is_flagged=False,
            attachments=attachments,
            in_reply_to=in_reply_to,
            message_id=message_id,
            references=references,
            folder="INBOX",
        )
    except Exception as e:
        try:
            current_app.logger.error(f"Error reading POP3 email {uid}: {e}")
        except RuntimeError:
            pass
        return None
    finally:
        try:
            pop3.quit()
        except Exception:
            pass


def _imap_read_email(uid: str, folder: str = None) -> Optional[EmailMessage]:
    config = _load_config()
    folder = folder or config.get("default_folder", "INBOX")

    imap = _get_imap_connection()
    try:
        status, _ = imap.select(f'"{folder}"')
        if status != "OK":
            return None

        status, data = imap.fetch(uid.encode(), "(FLAGS RFC822)")
        if status != "OK" or not data or not data[0]:
            return None

        raw_flags = ""
        raw_email = b""
        for part in data:
            if isinstance(part, tuple):
                if isinstance(part[0], bytes) and b"FLAGS" in part[0]:
                    raw_flags = part[0].decode("utf-8", errors="replace")
                raw_email = part[1] if len(part) > 1 else b""

        msg = email_lib.message_from_bytes(raw_email)

        subject = _decode_header(msg.get("Subject", ""))
        sender_name, sender_email = _parse_email_address(msg.get("From", ""))
        to = _decode_header(msg.get("To", ""))
        cc = _decode_header(msg.get("Cc", ""))
        date_str = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")
        in_reply_to = msg.get("In-Reply-To", "")
        references = msg.get("References", "")

        body_text, body_html = _extract_body(msg)
        attachments = _extract_attachments_info(msg)
        flags, is_read, is_flagged = _parse_flags(raw_flags)

        return EmailMessage(
            uid=uid,
            subject=subject or "(Sans sujet)",
            sender=sender_name,
            sender_email=sender_email,
            to=to,
            cc=cc,
            date=date_str,
            body_text=body_text,
            body_html=body_html,
            flags=flags,
            is_read=is_read,
            is_flagged=is_flagged,
            attachments=attachments,
            in_reply_to=in_reply_to,
            message_id=message_id,
            references=references,
            folder=folder,
        )
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def search_emails(
    query: str,
    folder: str = None,
    max_results: int = None,
) -> List[EmailEnvelope]:
    config = _load_config()
    folder = folder or config.get("default_folder", "INBOX")
    max_results = max_results or config.get("max_emails", 10)

    imap = _get_imap_connection()
    try:
        status, _ = imap.select(f'"{folder}"', readonly=True)
        if status != "OK":
            return []

        search_criteria = f'(OR OR FROM "{query}" SUBJECT "{query}" BODY "{query}")'

        status, data = imap.search(None, search_criteria)
        if status != "OK" or not data[0]:
            return []

        uid_list = data[0].split()[-max_results:]
        uid_list.reverse()

        envelopes = []
        for uid_bytes in uid_list:
            uid = uid_bytes.decode("utf-8")
            try:
                status, msg_data = imap.fetch(
                    uid_bytes,
                    "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])"
                )
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw_flags = ""
                raw_header = b""
                for part in msg_data:
                    if isinstance(part, tuple):
                        if isinstance(part[0], bytes):
                            raw_flags = part[0].decode("utf-8", errors="replace")
                        raw_header = part[1] if len(part) > 1 else b""

                msg = email_lib.message_from_bytes(raw_header)
                subject = _decode_header(msg.get("Subject", ""))
                sender_name, sender_email = _parse_email_address(msg.get("From", ""))
                to = _decode_header(msg.get("To", ""))
                date_str = msg.get("Date", "")
                flags, is_read, is_flagged = _parse_flags(raw_flags)

                envelopes.append(EmailEnvelope(
                    uid=uid,
                    subject=subject or "(Sans sujet)",
                    sender=sender_name,
                    sender_email=sender_email,
                    to=to,
                    date=date_str,
                    flags=flags,
                    is_read=is_read,
                    is_flagged=is_flagged,
                    folder=folder,
                ))
            except Exception:
                continue

        return envelopes
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    html: bool = False,
) -> bool:
    config = _load_config()
    from_addr = config.get("email_address", "")

    if not from_addr:
        raise ValueError("Adresse email de l'expéditeur non configurée")

    msg = email_lib.mime.multipart.MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = email_lib.utils.formatdate(localtime=True)
    msg["Message-ID"] = email_lib.utils.make_msgid()

    if cc:
        msg["Cc"] = cc

    if html:
        msg.attach(email_lib.mime.text.MIMEText(body, "html", "utf-8"))
    else:
        msg.attach(email_lib.mime.text.MIMEText(body, "plain", "utf-8"))

    recipients = [addr.strip() for addr in to.split(",")]
    if cc:
        recipients += [addr.strip() for addr in cc.split(",")]
    if bcc:
        recipients += [addr.strip() for addr in bcc.split(",")]

    smtp = _get_smtp_connection()
    try:
        smtp.sendmail(from_addr, recipients, msg.as_string())
        return True
    finally:
        try:
            smtp.quit()
        except Exception:
            pass


def reply_email(
    uid: str,
    body: str,
    reply_all: bool = False,
    folder: str = None,
) -> bool:
    original = read_email(uid, folder)
    if not original:
        raise ValueError(f"Email UID {uid} introuvable")

    config = _load_config()
    from_addr = config.get("email_address", "")

    subject = original.subject
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    to = original.sender_email
    cc = ""
    if reply_all and original.cc:
        cc_addrs = [
            addr.strip() for addr in original.cc.split(",")
            if from_addr.lower() not in addr.lower()
        ]
        cc = ", ".join(cc_addrs)

    msg = email_lib.mime.multipart.MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = email_lib.utils.formatdate(localtime=True)
    msg["Message-ID"] = email_lib.utils.make_msgid()
    msg["In-Reply-To"] = original.message_id
    refs = original.references
    if refs:
        msg["References"] = f"{refs} {original.message_id}"
    else:
        msg["References"] = original.message_id

    if cc:
        msg["Cc"] = cc

    msg.attach(email_lib.mime.text.MIMEText(body, "plain", "utf-8"))

    recipients = [to]
    if cc:
        recipients += [addr.strip() for addr in cc.split(",")]

    smtp = _get_smtp_connection()
    try:
        smtp.sendmail(from_addr, recipients, msg.as_string())
        return True
    finally:
        try:
            smtp.quit()
        except Exception:
            pass


def forward_email(
    uid: str,
    to: str,
    body: str = "",
    folder: str = None,
) -> bool:
    original = read_email(uid, folder)
    if not original:
        raise ValueError(f"Email UID {uid} introuvable")

    config = _load_config()

    subject = original.subject
    if not subject.lower().startswith("fwd:") and not subject.lower().startswith("fw:"):
        subject = f"Fwd: {subject}"

    forward_body = body + "\n\n" if body else ""
    forward_body += "---------- Message transféré ----------\n"
    forward_body += f"De : {original.sender} <{original.sender_email}>\n"
    forward_body += f"Date : {original.date}\n"
    forward_body += f"Sujet : {original.subject}\n"
    forward_body += f"À : {original.to}\n"
    forward_body += "----------------------------------------\n\n"
    forward_body += original.body_text or "(Contenu HTML uniquement)"

    return send_email(to=to, subject=subject, body=forward_body)


def draft_email(
    to: str = "",
    subject: str = "",
    body: str = "",
    folder: str = "Drafts",
) -> bool:
    config = _load_config()
    from_addr = config.get("email_address", "")

    msg = email_lib.mime.text.MIMEText(body, "plain", "utf-8")
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = email_lib.utils.formatdate(localtime=True)
    msg["Message-ID"] = email_lib.utils.make_msgid()

    imap = _get_imap_connection()
    try:
        draft_folders = [folder, "Drafts", "[Gmail]/Drafts", "INBOX.Drafts", "Brouillons"]
        for draft_folder in draft_folders:
            try:
                status, _ = imap.append(
                    f'"{draft_folder}"',
                    "\\Draft",
                    None,
                    msg.as_bytes(),
                )
                if status == "OK":
                    return True
            except Exception:
                continue
        return False
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def move_email(uid: str, dest_folder: str, source_folder: str = None) -> bool:
    config = _load_config()
    source_folder = source_folder or config.get("default_folder", "INBOX")

    imap = _get_imap_connection()
    try:
        status, _ = imap.select(f'"{source_folder}"')
        if status != "OK":
            return False

        status, _ = imap.copy(uid.encode(), f'"{dest_folder}"')
        if status != "OK":
            return False

        imap.store(uid.encode(), "+FLAGS", "\\Deleted")
        imap.expunge()
        return True
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def delete_email(uid: str, folder: str = None) -> bool:
    config = _load_config()
    folder = folder or config.get("default_folder", "INBOX")

    trash_folders = ["Trash", "[Gmail]/Trash", "INBOX.Trash", "Corbeille", "Deleted Messages"]
    for trash in trash_folders:
        try:
            if move_email(uid, trash, folder):
                return True
        except Exception:
            continue

    imap = _get_imap_connection()
    try:
        imap.select(f'"{folder}"')
        imap.store(uid.encode(), "+FLAGS", "\\Deleted")
        imap.expunge()
        return True
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def flag_email(uid: str, action: str, flag: str = "\\Seen", folder: str = None) -> bool:
    config = _load_config()
    folder = folder or config.get("default_folder", "INBOX")

    imap = _get_imap_connection()
    try:
        imap.select(f'"{folder}"')
        op = "+FLAGS" if action == "add" else "-FLAGS"
        status, _ = imap.store(uid.encode(), op, flag)
        return status == "OK"
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def add_tag(uid: str, tag: str, folder: str = None) -> bool:
    config = _load_config()
    folder = folder or config.get("default_folder", "INBOX")

    imap = _get_imap_connection()
    try:
        imap.select(f'"{folder}"')

        if "gmail" in config.get("imap_host", "").lower():
            try:
                status, _ = imap._simple_command(
                    "STORE", uid.encode(), "+X-GM-LABELS", f'("{tag}")'
                )
                if status == "OK":
                    return True
            except Exception:
                pass

        keyword = tag.replace(" ", "_")
        status, _ = imap.store(uid.encode(), "+FLAGS", keyword)
        return status == "OK"
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def remove_tag(uid: str, tag: str, folder: str = None) -> bool:
    config = _load_config()
    folder = folder or config.get("default_folder", "INBOX")

    imap = _get_imap_connection()
    try:
        imap.select(f'"{folder}"')

        if "gmail" in config.get("imap_host", "").lower():
            try:
                status, _ = imap._simple_command(
                    "STORE", uid.encode(), "-X-GM-LABELS", f'("{tag}")'
                )
                if status == "OK":
                    return True
            except Exception:
                pass

        keyword = tag.replace(" ", "_")
        status, _ = imap.store(uid.encode(), "-FLAGS", keyword)
        return status == "OK"
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def list_tags() -> List[str]:
    config = _load_config()
    tags = []

    imap = _get_imap_connection()
    try:
        if "gmail" in config.get("imap_host", "").lower():
            status, folder_list = imap.list()
            if status == "OK":
                for item in folder_list:
                    if isinstance(item, bytes):
                        item = item.decode("utf-8", errors="replace")
                    match = re.match(r'\(([^)]*)\)\s+"([^"]+)"\s+"?([^"]+)"?', str(item))
                    if match:
                        name = match.group(3).strip('"')
                        if name.startswith("[Gmail]"):
                            label = name.replace("[Gmail]/", "")
                            if label != "[Gmail]":
                                tags.append(label)
                        else:
                            tags.append(name)
        else:
            status, _ = imap.select("INBOX", readonly=True)
            if status == "OK":
                status, folder_list = imap.list()
                if status == "OK":
                    for item in folder_list:
                        if isinstance(item, bytes):
                            item = item.decode("utf-8", errors="replace")
                        match = re.match(r'\(([^)]*)\)\s+"([^"]+)"\s+"?([^"]+)"?', str(item))
                        if match:
                            name = match.group(3).strip('"')
                            if "\\Noselect" not in match.group(1):
                                tags.append(name)

        return sorted(set(tags))
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def get_attachments_info(uid: str, folder: str = None) -> List[Dict[str, Any]]:
    msg = read_email(uid, folder)
    if not msg:
        return []
    return msg.attachments


def get_email_stats() -> Dict[str, Any]:
    stats = {
        "total": 0,
        "unread": 0,
        "folders": [],
    }

    imap = _get_imap_connection()
    try:
        status, folder_list = imap.list()
        if status != "OK":
            return stats

        for item in folder_list:
            if isinstance(item, bytes):
                item = item.decode("utf-8", errors="replace")

            match = re.match(r'\(([^)]*)\)\s+"([^"]+)"\s+"?([^"]+)"?', str(item))
            if not match:
                continue

            flags_str, _, name = match.groups()
            name = name.strip('"')

            if "\\Noselect" in flags_str:
                continue

            try:
                stat_status, stat_data = imap.status(
                    f'"{name}"', "(MESSAGES UNSEEN)"
                )
                if stat_status == "OK" and stat_data[0]:
                    stat_str = stat_data[0]
                    if isinstance(stat_str, bytes):
                        stat_str = stat_str.decode("utf-8", errors="replace")
                    msg_match = re.search(r'MESSAGES\s+(\d+)', stat_str)
                    unseen_match = re.search(r'UNSEEN\s+(\d+)', stat_str)

                    total = int(msg_match.group(1)) if msg_match else 0
                    unread = int(unseen_match.group(1)) if unseen_match else 0

                    stats["folders"].append({
                        "name": name,
                        "total": total,
                        "unread": unread,
                    })
                    stats["total"] += total
                    stats["unread"] += unread
            except Exception:
                continue

        return stats
    finally:
        try:
            imap.logout()
        except Exception:
            pass
