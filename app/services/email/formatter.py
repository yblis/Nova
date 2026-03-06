import re
from typing import List, Dict, Any, Tuple

from flask import current_app

from .models import EmailEnvelope, EmailMessage
from .operations import (
    read_email, send_email, reply_email, forward_email,
    move_email, delete_email, flag_email, add_tag, remove_tag,
)


def format_email_context(emails: List[EmailEnvelope]) -> str:
    if not emails:
        return ""

    lines = ["=== EMAILS RÉCENTS DE L'UTILISATEUR ===\n"]

    for i, em in enumerate(emails, 1):
        status = "📩" if not em.is_read else "📧"
        flag = " ⭐" if em.is_flagged else ""
        attach = " 📎" if em.has_attachments else ""

        lines.append(f"[{i}] {status}{flag}{attach} {em.subject}")
        lines.append(f"    De : {em.sender} <{em.sender_email}>")
        lines.append(f"    Date : {em.date}")
        lines.append(f"    Dossier : {em.folder}")
        if not em.is_read:
            lines.append("    Statut : NON LU")
        lines.append("")

    lines.append("=== FIN DES EMAILS ===\n")
    lines.append(
        "Tu peux utiliser les fonctions suivantes sur ces emails : "
        "lire le contenu complet, répondre, transférer, supprimer, "
        "déplacer vers un dossier, marquer lu/non-lu/important, "
        "ajouter/retirer des tags, chercher d'autres emails, "
        "et envoyer de nouveaux emails.\n"
    )

    return "\n".join(lines)


def format_full_email_context(email_msg: EmailMessage) -> str:
    lines = [
        f"=== EMAIL COMPLET (UID: {email_msg.uid}) ===",
        f"Sujet : {email_msg.subject}",
        f"De : {email_msg.sender} <{email_msg.sender_email}>",
        f"À : {email_msg.to}",
    ]

    if email_msg.cc:
        lines.append(f"Cc : {email_msg.cc}")

    lines.append(f"Date : {email_msg.date}")

    if email_msg.attachments:
        attach_list = ", ".join(
            f"{a['filename']} ({a['content_type']}, {a['size']} octets)"
            for a in email_msg.attachments
        )
        lines.append(f"Pièces jointes : {attach_list}")

    lines.append(f"\n--- Contenu ---\n{email_msg.body_text or '(Contenu HTML uniquement)'}")
    lines.append("=== FIN EMAIL ===\n")

    return "\n".join(lines)


def get_email_actions_prompt() -> str:
    return """
PRÉSENTATION DES EMAILS :
- Quand l'utilisateur demande de voir ses emails, affiche-les dans un TABLEAU MARKDOWN avec les colonnes : | # | De | Sujet | Date | Lu |
- Ne fais JAMAIS de résumé des emails sauf si explicitement demandé.
- Utilise les emojis 📩 (non lu) et 📧 (lu) dans la colonne Lu.

ACTIONS EMAIL :
Tu peux exécuter des actions en incluant ces tags dans ta réponse (une par ligne) :
[EMAIL_ACTION:delete:uid=UID]
[EMAIL_ACTION:move:uid=UID:dest=DOSSIER]
[EMAIL_ACTION:flag:uid=UID:action=add:flag=\\Seen]
[EMAIL_ACTION:flag:uid=UID:action=remove:flag=\\Seen]
[EMAIL_ACTION:flag:uid=UID:action=add:flag=\\Flagged]
[EMAIL_ACTION:send:to=EMAIL:subject=SUJET:body=CONTENU]
[EMAIL_ACTION:reply:uid=UID:body=CONTENU]
[EMAIL_ACTION:reply_all:uid=UID:body=CONTENU]
[EMAIL_ACTION:forward:uid=UID:to=EMAIL:body=NOTE]
[EMAIL_ACTION:tag_add:uid=UID:tag=NOM]
[EMAIL_ACTION:tag_remove:uid=UID:tag=NOM]

Inclus TOUJOURS le tag quand on te demande une action. Les tags sont exécutés automatiquement.
"""


def parse_email_actions(text: str) -> List[Dict[str, Any]]:
    actions = []

    pattern = r'\[EMAIL_ACTION:([^\]]+)\]'

    for match in re.finditer(pattern, text):
        raw = match.group(1)
        parts = raw.split(":")

        if len(parts) < 2:
            continue

        action_type = parts[0].strip()

        params = {"type": action_type, "raw": match.group(0)}
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                params[key.strip()] = value.strip()

        actions.append(params)

    return actions


def execute_email_action(action: Dict[str, Any]) -> Dict[str, Any]:
    action_type = action.get("type", "")
    uid = action.get("uid", "")
    result = {"action_type": action_type, "success": False, "message": ""}

    try:
        if action_type == "delete":
            if not uid:
                result["message"] = "UID manquant pour la suppression"
                return result
            delete_email(uid)
            result["success"] = True
            result["message"] = f"Email {uid} supprimé (déplacé dans Corbeille)"

        elif action_type == "move":
            dest = action.get("dest", "")
            if not uid or not dest:
                result["message"] = "UID ou dossier destination manquant"
                return result
            move_email(uid, dest)
            result["success"] = True
            result["message"] = f"Email {uid} déplacé vers {dest}"

        elif action_type == "flag":
            flag_action = action.get("action", "add")
            flag = action.get("flag", "\\Seen")
            if not uid:
                result["message"] = "UID manquant pour le flag"
                return result
            flag_email(uid, flag_action, flag)
            result["success"] = True
            flag_label = "ajouté" if flag_action == "add" else "retiré"
            result["message"] = f"Flag {flag} {flag_label} sur l'email {uid}"

        elif action_type == "send":
            to = action.get("to", "")
            subject = action.get("subject", "")
            body = action.get("body", "").replace("\\n", "\n")
            if not to:
                result["message"] = "Destinataire manquant"
                return result
            send_email(to=to, subject=subject, body=body)
            result["success"] = True
            result["message"] = f"Email envoyé à {to}"

        elif action_type in ("reply", "reply_all"):
            body = action.get("body", "").replace("\\n", "\n")
            if not uid:
                result["message"] = "UID manquant pour la réponse"
                return result
            reply_all_flag = action_type == "reply_all"
            reply_email(uid=uid, body=body, reply_all=reply_all_flag)
            result["success"] = True
            result["message"] = f"Réponse {'à tous ' if reply_all_flag else ''}envoyée (email {uid})"

        elif action_type == "forward":
            to = action.get("to", "")
            body = action.get("body", "").replace("\\n", "\n")
            if not uid or not to:
                result["message"] = "UID ou destinataire manquant"
                return result
            forward_email(uid=uid, to=to, body=body)
            result["success"] = True
            result["message"] = f"Email {uid} transféré à {to}"

        elif action_type == "tag_add":
            tag = action.get("tag", "")
            if not uid or not tag:
                result["message"] = "UID ou tag manquant"
                return result
            add_tag(uid, tag)
            result["success"] = True
            result["message"] = f"Tag '{tag}' ajouté à l'email {uid}"

        elif action_type == "tag_remove":
            tag = action.get("tag", "")
            if not uid or not tag:
                result["message"] = "UID ou tag manquant"
                return result
            remove_tag(uid, tag)
            result["success"] = True
            result["message"] = f"Tag '{tag}' retiré de l'email {uid}"

        else:
            result["message"] = f"Type d'action inconnu : {action_type}"

    except Exception as e:
        result["message"] = f"Erreur lors de l'exécution : {str(e)}"
        try:
            current_app.logger.error(f"Email action error ({action_type}): {e}")
        except RuntimeError:
            pass

    return result


def execute_all_email_actions(text: str) -> Tuple[List[Dict[str, Any]], str]:
    actions = parse_email_actions(text)
    results = []
    cleaned_text = text

    for action in actions:
        result = execute_email_action(action)
        results.append(result)
        raw_tag = action.get("raw", "")
        if raw_tag:
            cleaned_text = cleaned_text.replace(raw_tag, "")

    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()

    return results, cleaned_text
