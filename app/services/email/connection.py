import imaplib
import poplib
import smtplib
import ssl

from .config import _load_config


def _get_imap_connection() -> imaplib.IMAP4:
    from ..crypto_service import decrypt_api_key

    config = _load_config()
    host = config.get("imap_host", "")
    port = config.get("imap_port", 993)
    encryption = config.get("imap_encryption", "tls")
    email_addr = config.get("email_address", "")
    timeout = config.get("timeout", 15)

    if not host or not email_addr:
        raise ValueError("Configuration IMAP incomplète (hôte ou email manquant)")

    password = decrypt_api_key(config.get("password_encrypted", ""))
    if not password:
        raise ValueError("Mot de passe email non configuré ou déchiffrement échoué")

    try:
        if encryption == "tls":
            ctx = ssl.create_default_context()
            imap = imaplib.IMAP4_SSL(host, port, timeout=timeout, ssl_context=ctx)
        elif encryption == "starttls":
            imap = imaplib.IMAP4(host, port, timeout=timeout)
            imap.starttls(ssl.create_default_context())
        else:
            imap = imaplib.IMAP4(host, port, timeout=timeout)

        imap.login(email_addr, password)
        return imap
    except imaplib.IMAP4.error as e:
        raise ConnectionError(f"Échec de connexion IMAP: {e}")
    except Exception as e:
        raise ConnectionError(f"Erreur IMAP: {e}")


def _get_pop3_connection() -> poplib.POP3:
    from ..crypto_service import decrypt_api_key

    config = _load_config()
    host = config.get("pop3_host", "")
    port = config.get("pop3_port", 995)
    encryption = config.get("pop3_encryption", "tls")
    email_addr = config.get("email_address", "")
    timeout = config.get("timeout", 15)

    if not host or not email_addr:
        raise ValueError("Configuration POP3 incomplète (hôte ou email manquant)")

    password = decrypt_api_key(config.get("password_encrypted", ""))
    if not password:
        raise ValueError("Mot de passe email non configuré ou déchiffrement échoué")

    try:
        if encryption == "tls":
            ctx = ssl.create_default_context()
            pop3 = poplib.POP3_SSL(host, port, timeout=timeout, context=ctx)
        else:
            pop3 = poplib.POP3(host, port, timeout=timeout)

        pop3.user(email_addr)
        pop3.pass_(password)
        return pop3
    except poplib.error_proto as e:
        raise ConnectionError(f"Échec de connexion POP3: {e}")
    except Exception as e:
        raise ConnectionError(f"Erreur POP3: {e}")


def _get_smtp_connection() -> smtplib.SMTP:
    from ..crypto_service import decrypt_api_key

    config = _load_config()
    host = config.get("smtp_host", "")
    port = config.get("smtp_port", 587)
    encryption = config.get("smtp_encryption", "starttls")
    email_addr = config.get("email_address", "")
    timeout = config.get("timeout", 15)

    if not host or not email_addr:
        raise ValueError("Configuration SMTP incomplète")

    password = decrypt_api_key(config.get("password_encrypted", ""))
    if not password:
        raise ValueError("Mot de passe email non configuré")

    try:
        if encryption == "tls":
            ctx = ssl.create_default_context()
            smtp = smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx)
        else:
            smtp = smtplib.SMTP(host, port, timeout=timeout)
            if encryption == "starttls":
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()

        smtp.login(email_addr, password)
        return smtp
    except smtplib.SMTPAuthenticationError as e:
        raise ConnectionError(f"Échec d'authentification SMTP: {e}")
    except Exception as e:
        raise ConnectionError(f"Erreur SMTP: {e}")
