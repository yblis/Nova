from .models import EmailEnvelope, EmailMessage, EmailFolder
from .config import (
    _load_config, _save_config, _get_config_path,
    get_config, set_config, get_presets, EMAIL_PRESETS,
)
from .connection import _get_imap_connection, _get_pop3_connection, _get_smtp_connection
from .parser import (
    _decode_header, _parse_email_address, _extract_body,
    _extract_attachments_info, _parse_flags,
)
from .operations import (
    is_email_available, list_folders, list_emails,
    read_email, search_emails, send_email, reply_email,
    forward_email, draft_email, move_email, delete_email,
    flag_email, add_tag, remove_tag, list_tags,
    get_attachments_info, get_email_stats,
)
from .formatter import (
    format_email_context, format_full_email_context,
    get_email_actions_prompt, parse_email_actions,
    execute_email_action, execute_all_email_actions,
)
