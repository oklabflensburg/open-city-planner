import logging
import smtplib
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


def send_email(to_email: str, subject: str, html: str, text: str) -> None:
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
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)


def display_name(user: User) -> str:
    return user.display_name or " ".join(part for part in [user.first_name, user.last_name] if part).strip() or user.email


def send_verification_email(user: User, token: str) -> None:
    settings = get_settings()
    link = f"{settings.app_base_url.rstrip('/')}/email-bestaetigen?token={token}"
    html, text = render_pair("verify_email", {"user": user, "name": display_name(user), "link": link})
    send_email(user.email, "E-Mail-Adresse bestätigen – OK Lab Flensburg", html, text)


def send_password_reset_email(user: User, token: str) -> None:
    settings = get_settings()
    link = f"{settings.app_base_url.rstrip('/')}/passwort-zuruecksetzen?token={token}"
    html, text = render_pair("password_reset", {"user": user, "name": display_name(user), "link": link, "minutes": settings.password_reset_expire_minutes})
    send_email(user.email, "Passwort zurücksetzen – OK Lab Flensburg", html, text)


def send_password_changed_email(user: User) -> None:
    html, text = render_pair("password_changed", {"user": user, "name": display_name(user)})
    send_email(user.email, "Passwort geändert – OK Lab Flensburg", html, text)
