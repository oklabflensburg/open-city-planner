import logging
import smtplib
from email.headerregistry import Address
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import get_settings
from app.models.user import User

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "email"
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_pair(template: str, context: dict[str, object]) -> tuple[str, str]:
    return (
        env.get_template(f"{template}.html").render(**context),
        env.get_template(f"{template}.txt").render(**context),
    )


def send_email(
    to_email: str,
    subject: str,
    html: str,
    text: str,
    *,
    to_name: str | None = None,
    reply_to: str | None = None,
) -> None:
    settings = get_settings()
    if settings.email_backend == "console":
        logger.info("Console email to=%s subject=%s\n%s", to_email, subject, text)
        return
    if settings.email_backend != "smtp":
        raise RuntimeError("Unsupported EMAIL_BACKEND")
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST must be configured for smtp email backend")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = Address(
        display_name=settings.smtp_from_name,
        addr_spec=settings.smtp_from_email,
    )
    message["To"] = Address(display_name=to_name or "", addr_spec=to_email)
    if reply_to:
        message["Reply-To"] = Address(addr_spec=reply_to)
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)


def display_name(user: User) -> str:
    return (
        user.display_name
        or " ".join(part for part in [user.first_name, user.last_name] if part).strip()
        or user.email
    )


def send_verification_email(user: User, token: str) -> None:
    settings = get_settings()
    link = f"{settings.app_base_url.rstrip('/')}/email-bestaetigen?token={token}"
    html, text = render_pair(
        "verify_email", {"user": user, "name": display_name(user), "link": link}
    )
    send_email(user.email, "E-Mail-Adresse bestätigen – OK Lab Flensburg", html, text)


def send_password_reset_email(user: User, token: str) -> None:
    settings = get_settings()
    link = f"{settings.app_base_url.rstrip('/')}/passwort-zuruecksetzen?token={token}"
    html, text = render_pair(
        "password_reset",
        {
            "user": user,
            "name": display_name(user),
            "link": link,
            "minutes": settings.password_reset_expire_minutes,
        },
    )
    send_email(user.email, "Passwort zurücksetzen – OK Lab Flensburg", html, text)


def send_password_changed_email(user: User) -> None:
    html, text = render_pair("password_changed", {"user": user, "name": display_name(user)})
    send_email(user.email, "Passwort geändert – OK Lab Flensburg", html, text)


def send_mfa_security_email(user: User, event: str) -> None:
    labels = {
        "enabled": (
            "Zwei-Faktor-Authentifizierung aktiviert",
            "Die Zwei-Faktor-Authentifizierung Ihres Kontos wurde aktiviert.",
        ),
        "disabled": (
            "Zwei-Faktor-Authentifizierung deaktiviert",
            "Die Zwei-Faktor-Authentifizierung Ihres Kontos wurde deaktiviert.",
        ),
        "recovery_regenerated": (
            "Neue Wiederherstellungscodes erzeugt",
            "Für Ihr Konto wurden neue Wiederherstellungscodes erzeugt. Alle bisherigen Codes sind ungültig.",
        ),
        "recovery_used": (
            "Wiederherstellungscode verwendet",
            "Für die Anmeldung bei Ihrem Konto wurde ein Wiederherstellungscode verwendet.",
        ),
        "passkey_added": (
            "Passkey hinzugefügt",
            "Für Ihr Konto wurde ein neuer Passkey hinzugefügt. Falls Sie diese Änderung nicht vorgenommen haben, prüfen Sie bitte umgehend Ihre Kontosicherheit.",
        ),
        "passkey_removed": (
            "Passkey entfernt",
            "Ein Passkey wurde aus Ihrem Konto entfernt. Falls Sie diese Änderung nicht vorgenommen haben, prüfen Sie bitte umgehend Ihre Kontosicherheit.",
        ),
        "passkeys_removed": (
            "Alle Passkeys entfernt",
            "Der letzte Passkey wurde aus Ihrem Konto entfernt. Falls Sie diese Änderung nicht vorgenommen haben, prüfen Sie bitte umgehend Ihre Kontosicherheit.",
        ),
    }
    subject, message = labels[event]
    html, text = render_pair(
        "mfa_security",
        {"user": user, "name": display_name(user), "message": message},
    )
    send_email(user.email, f"{subject} – OK Lab Flensburg", html, text)


def send_contact_notification(
    *,
    name: str,
    email: str,
    subject: str,
    message: str,
    received_at: str,
) -> None:
    settings = get_settings()
    if not settings.contact_to_email:
        raise RuntimeError("CONTACT_TO_EMAIL must be configured")
    context = {
        "name": name,
        "email": email,
        "subject": subject,
        "message": message,
        "received_at": received_at,
    }
    html, text = render_pair("contact_notification", context)
    send_email(
        settings.contact_to_email,
        f"[Stadtplaner Kontakt] {subject}",
        html,
        text,
        to_name=settings.contact_to_name,
        reply_to=email,
    )


def send_contact_copy(*, name: str, email: str, subject: str, message: str) -> None:
    html, text = render_pair(
        "contact_copy",
        {"name": name, "subject": subject, "message": message},
    )
    send_email(email, "Kopie Ihrer Nachricht an Stadtplaner", html, text, to_name=name)
