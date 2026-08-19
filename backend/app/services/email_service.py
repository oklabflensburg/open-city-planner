import asyncio
import logging
import re
import smtplib
from dataclasses import dataclass
from email.headerregistry import Address
from email.message import EmailMessage
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, StrictUndefined, meta, nodes, select_autoescape
from jinja2.sandbox import SandboxedEnvironment
from markupsafe import Markup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.email_template import EmailTemplate
from app.models.user import User

logger = logging.getLogger(__name__)
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "email"
SUBJECT_MAX_LENGTH = 200
BODY_MAX_LENGTH = 50_000
TemplateCategory = Literal["Sicherheit", "Konto", "Kontakt"]


@dataclass(frozen=True)
class EmailTemplateDefinition:
    key: str
    name: str
    description: str
    category: TemplateCategory
    default_subject: str
    default_html: str
    default_text: str
    allowed_variables: frozenset[str]
    required_variables: frozenset[str] = frozenset()
    is_security_sensitive: bool = False
    is_active: bool = True


@dataclass(frozen=True)
class EmailTemplateContent:
    subject: str
    html_body: str
    text_body: str
    customized: bool
    version: int


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


class EmailTemplateValidationError(ValueError):
    def __init__(self, code: str, message: str, **details: str) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


EMAIL_TEMPLATE_REGISTRY: dict[str, EmailTemplateDefinition] = {
    "verify_email": EmailTemplateDefinition(
        "verify_email",
        "E-Mail-Adresse bestätigen",
        "Bestätigung einer neu hinterlegten E-Mail-Adresse.",
        "Sicherheit",
        "E-Mail-Adresse bestätigen – OK Lab Flensburg",
        """<p>Hallo {{ name }},</p><p>Vielen Dank für Ihre Registrierung. Bitte bestätigen Sie Ihre E-Mail-Adresse:</p><p><a class="email-button" href="{{ verification_url }}">E-Mail-Adresse bestätigen</a></p><p>Der Link ist nur begrenzt gültig. Wenn Sie kein Konto erstellt haben, können Sie diese Nachricht ignorieren.</p>""",
        """Hallo {{ name }},\n\nvielen Dank für Ihre Registrierung.\n\nBitte bestätigen Sie Ihre E-Mail-Adresse:\n{{ verification_url }}\n\nDer Link ist nur begrenzt gültig. Wenn Sie kein Konto erstellt haben, können Sie diese Nachricht ignorieren.""",
        frozenset({"name", "verification_url"}),
        frozenset({"verification_url"}),
        True,
    ),
    "password_reset": EmailTemplateDefinition(
        "password_reset",
        "Passwort zurücksetzen",
        "Sicherer Link zum Zurücksetzen eines Passworts.",
        "Sicherheit",
        "Passwort zurücksetzen – OK Lab Flensburg",
        """<p>Hallo {{ name }},</p><p>Für Ihr Stadtplaner-Konto wurde das Zurücksetzen des Passworts angefordert.</p><p><a class="email-button" href="{{ reset_url }}">Passwort zurücksetzen</a></p><p>Der Link ist {{ expires_minutes }} Minuten gültig. Wenn Sie die Anfrage nicht gestellt haben, ist keine Aktion erforderlich.</p>""",
        """Hallo {{ name }},\n\nfür Ihr Stadtplaner-Konto wurde das Zurücksetzen des Passworts angefordert.\n\nPasswort zurücksetzen:\n{{ reset_url }}\n\nDer Link ist {{ expires_minutes }} Minuten gültig. Wenn Sie die Anfrage nicht gestellt haben, ist keine Aktion erforderlich.""",
        frozenset({"name", "reset_url", "expires_minutes"}),
        frozenset({"reset_url"}),
        True,
    ),
    "password_changed": EmailTemplateDefinition(
        "password_changed",
        "Passwort geändert",
        "Sicherheitshinweis nach einer Passwortänderung.",
        "Sicherheit",
        "Passwort geändert – OK Lab Flensburg",
        """<p>Hallo {{ name }},</p><p>Ihr Passwort wurde geändert.</p><p>Wenn Sie diese Änderung nicht ausgelöst haben, kontaktieren Sie bitte das OK Lab Flensburg.</p>""",
        """Hallo {{ name }},\n\nIhr Passwort wurde geändert.\n\nWenn Sie diese Änderung nicht ausgelöst haben, kontaktieren Sie bitte das OK Lab Flensburg.""",
        frozenset({"name"}),
        is_security_sensitive=True,
    ),
    "mfa_security": EmailTemplateDefinition(
        "mfa_security",
        "MFA- und Passkey-Sicherheit",
        "Hinweise zu MFA, Wiederherstellungscodes und Passkeys.",
        "Sicherheit",
        "{{ security_event_title }} – OK Lab Flensburg",
        """<p>Hallo {{ name }},</p><h1>{{ security_event_title }}</h1><p>{{ security_event_message }}</p><p>Falls Sie diese Änderung nicht selbst vorgenommen haben, ändern Sie bitte umgehend Ihr Passwort und wenden Sie sich an den Support.</p>""",
        """Hallo {{ name }},\n\n{{ security_event_title }}\n\n{{ security_event_message }}\n\nFalls Sie diese Änderung nicht selbst vorgenommen haben, ändern Sie bitte umgehend Ihr Passwort und wenden Sie sich an den Support.""",
        frozenset({"name", "security_event_title", "security_event_message"}),
        is_security_sensitive=True,
    ),
    "contact_notification": EmailTemplateDefinition(
        "contact_notification",
        "Kontaktformular – interne Benachrichtigung",
        "Interne Nachricht über eine neue Kontaktanfrage.",
        "Kontakt",
        "[Stadtplaner Kontakt] {{ subject }}",
        """<h1>Neue Kontaktanfrage über Stadtplaner</h1><p><strong>Name:</strong><br>{{ name }}</p><p><strong>E-Mail:</strong><br>{{ email }}</p><p><strong>Betreff:</strong><br>{{ subject }}</p><p><strong>Nachricht:</strong></p><blockquote>{{ message }}</blockquote><p><strong>Eingegangen:</strong> {{ received_at }}</p>""",
        """Neue Kontaktanfrage über Stadtplaner\n\nName: {{ name }}\nE-Mail: {{ email }}\nBetreff: {{ subject }}\n\nNachricht:\n{{ message }}\n\nEingegangen: {{ received_at }}""",
        frozenset({"name", "email", "subject", "message", "received_at"}),
    ),
    "contact_copy": EmailTemplateDefinition(
        "contact_copy",
        "Kontaktformular – Kopie an Absender",
        "Bestätigung und Kopie einer Kontaktanfrage.",
        "Kontakt",
        "Kopie Ihrer Nachricht an Stadtplaner",
        """<p>Hallo {{ name }},</p><p>Vielen Dank für Ihre Nachricht. Dies ist eine Kopie Ihrer Anfrage:</p><p><strong>Betreff:</strong><br>{{ subject }}</p><p><strong>Nachricht:</strong></p><blockquote>{{ message }}</blockquote><p>Ihre Nachricht wurde an das Stadtplaner-Team übermittelt.</p>""",
        """Hallo {{ name }},\n\nvielen Dank für Ihre Nachricht. Dies ist eine Kopie Ihrer Anfrage:\n\nBetreff: {{ subject }}\n\nNachricht:\n{{ message }}\n\nIhre Nachricht wurde an das Stadtplaner-Team übermittelt.""",
        frozenset({"name", "subject", "message"}),
    ),
    "welcome": EmailTemplateDefinition(
        "welcome",
        "Willkommensmail",
        "Willkommensmail nach der erstmaligen Bestätigung eines Kontos.",
        "Konto",
        "Willkommen beim Stadtplaner – OK Lab Flensburg",
        """<p>Hallo {{ name }},</p><p>willkommen beim Stadtplaner des OK Lab Flensburg.</p><p>Mit dem Stadtplaner können Sie Flächen erfassen, offene Geodaten nutzen und gemeinsam an einem besseren Überblick über Flensburg arbeiten.</p><p><a class="email-button" href="{{ app_url }}">Zum Stadtplaner</a></p><p><a href="{{ documentation_url }}">Dokumentation öffnen</a></p><p>Bei Fragen oder wenn Sie mitmachen möchten, finden Sie weitere Informationen in der Dokumentation.</p><p>Viele Grüße<br>OK Lab Flensburg</p>""",
        """Hallo {{ name }},\n\nwillkommen beim Stadtplaner des OK Lab Flensburg.\n\nMit dem Stadtplaner können Sie Flächen erfassen, offene Geodaten nutzen und gemeinsam an einem besseren Überblick über Flensburg arbeiten.\n\nZum Stadtplaner:\n{{ app_url }}\n\nDokumentation:\n{{ documentation_url }}\n\nBei Fragen oder wenn Sie mitmachen möchten, finden Sie weitere Informationen in der Dokumentation.\n\nViele Grüße\nOK Lab Flensburg""",
        frozenset({"name", "app_url", "documentation_url", "profile_url"}),
        frozenset({"app_url", "documentation_url"}),
    ),
}

_sandbox = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)
_sandbox.filters.clear()
_sandbox.tests.clear()
_text_sandbox = SandboxedEnvironment(autoescape=False, undefined=StrictUndefined)
_text_sandbox.filters.clear()
_text_sandbox.tests.clear()
_layout_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    undefined=StrictUndefined,
)
_DISALLOWED_NODES = (
    nodes.Call,
    nodes.Getattr,
    nodes.Getitem,
    nodes.Filter,
    nodes.Test,
    nodes.Include,
    nodes.Import,
    nodes.FromImport,
    nodes.Extends,
    nodes.Macro,
    nodes.Assign,
    nodes.For,
)
_ALLOWED_TAGS = {"p", "br", "strong", "em", "ul", "ol", "li", "h1", "h2", "h3", "a", "blockquote"}
_BUTTON_STYLE = (
    "background:#154d73;color:#ffffff;text-decoration:none;padding:12px 18px;"
    "border-radius:6px;font-weight:bold;display:inline-block;"
)


def _safe_href(value: str) -> bool:
    if re.fullmatch(r"{{\s*[a-zA-Z_][a-zA-Z0-9_]*\s*}}", value):
        return True
    parsed = urlsplit(value.strip())
    if parsed.scheme == "mailto":
        return bool(parsed.path)
    if parsed.scheme == "https":
        return bool(parsed.netloc)
    return parsed.scheme == "http" and bool(parsed.netloc) and not get_settings().production


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.open_tags: list[str] = []
        self.suppressed_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "iframe", "object", "embed", "form", "svg", "math"}:
            self.suppressed_depth += 1
            return
        if self.suppressed_depth:
            return
        if tag not in _ALLOWED_TAGS:
            return
        values = {name.lower(): value or "" for name, value in attrs}
        rendered_attrs: list[str] = []
        if tag == "a":
            href = values.get("href", "")
            if _safe_href(href):
                rendered_attrs.append(f'href="{escape(href, quote=True)}"')
            if values.get("class") == "email-button" or values.get("style") == _BUTTON_STYLE:
                rendered_attrs.append(f'style="{_BUTTON_STYLE}"')
        suffix = f" {' '.join(rendered_attrs)}" if rendered_attrs else ""
        self.parts.append(f"<{tag}{suffix}>")
        if tag != "br":
            self.open_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.suppressed_depth:
            if tag in {"script", "style", "iframe", "object", "embed", "form", "svg", "math"}:
                self.suppressed_depth -= 1
            return
        if tag in self.open_tags:
            while self.open_tags:
                current = self.open_tags.pop()
                self.parts.append(f"</{current}>")
                if current == tag:
                    break

    def handle_data(self, data: str) -> None:
        if self.suppressed_depth:
            return
        self.parts.append(escape(data))

    def result(self) -> str:
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts)


def sanitize_email_html(value: str) -> str:
    sanitizer = _Sanitizer()
    sanitizer.feed(value)
    sanitizer.close()
    return sanitizer.result()


def global_email_context() -> dict[str, str]:
    settings = get_settings()
    base_url = settings.app_base_url.rstrip("/")
    return {
        "site_name": "Stadtplaner",
        "app_base_url": base_url,
        "logo_url": f"{base_url}/branding/ok-lab-flensburg-email.png",
        "imprint_url": f"{base_url}/impressum",
        "privacy_url": f"{base_url}/datenschutz",
        "support_email": settings.contact_to_email or settings.smtp_from_email,
    }


def template_definition(key: str) -> EmailTemplateDefinition:
    try:
        return EMAIL_TEMPLATE_REGISTRY[key]
    except KeyError as exc:
        raise LookupError("Die E-Mail-Vorlage wurde nicht gefunden.") from exc


def _validate_jinja(source: str, definition: EmailTemplateDefinition, field: str) -> set[str]:
    try:
        tree = _sandbox.parse(source)
    except Exception as exc:
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_SYNTAX_INVALID", f"{field} enthält ungültige Template-Syntax."
        ) from exc
    if any(tree.find_all(_DISALLOWED_NODES)):
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_EXPRESSION_NOT_ALLOWED",
            f"{field} enthält einen nicht erlaubten Template-Ausdruck.",
        )
    variables = meta.find_undeclared_variables(tree)
    unknown = sorted(variables - definition.allowed_variables)
    if unknown:
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED",
            f"Die Variable {unknown[0]} ist für diese Vorlage nicht erlaubt.",
            variable=unknown[0],
        )
    return variables


def validate_template_content(
    definition: EmailTemplateDefinition, subject: str, html_body: str, text_body: str
) -> tuple[str, str, str]:
    if "\r" in subject or "\n" in subject:
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_SUBJECT_INVALID", "Der Betreff darf keinen Zeilenumbruch enthalten."
        )
    if len(subject) > SUBJECT_MAX_LENGTH:
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_SUBJECT_TOO_LONG", "Der Betreff darf höchstens 200 Zeichen lang sein."
        )
    if len(html_body) > BODY_MAX_LENGTH or len(text_body) > BODY_MAX_LENGTH:
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_BODY_TOO_LONG", "Vorlageninhalte dürfen höchstens 50 KB groß sein."
        )
    _validate_jinja(subject, definition, "Der Betreff")
    html_variables = _validate_jinja(html_body, definition, "Der HTML-Inhalt")
    text_variables = _validate_jinja(text_body, definition, "Der Text-Inhalt")
    missing = sorted(
        (definition.required_variables - html_variables)
        | (definition.required_variables - text_variables)
    )
    if missing:
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_REQUIRED_VARIABLE_MISSING",
            f"Die erforderliche Variable {missing[0]} fehlt.",
            variable=missing[0],
        )
    sanitized_html = sanitize_email_html(html_body.strip())
    sanitized_variables = _validate_jinja(sanitized_html, definition, "Der bereinigte HTML-Inhalt")
    missing_after_sanitization = sorted(definition.required_variables - sanitized_variables)
    if missing_after_sanitization:
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_REQUIRED_VARIABLE_MISSING",
            f"Die erforderliche Variable {missing_after_sanitization[0]} fehlt im sicheren HTML-Inhalt.",
            variable=missing_after_sanitization[0],
        )
    return subject.strip(), sanitized_html, text_body.strip()


def default_template_content(definition: EmailTemplateDefinition) -> EmailTemplateContent:
    return EmailTemplateContent(
        definition.default_subject, definition.default_html, definition.default_text, False, 0
    )


async def get_template_content(session: AsyncSession | None, key: str) -> EmailTemplateContent:
    definition = template_definition(key)
    if session is None:
        return default_template_content(definition)
    record = await session.scalar(select(EmailTemplate).where(EmailTemplate.key == key))
    if record is None:
        return default_template_content(definition)
    return EmailTemplateContent(
        record.subject,
        record.html_body,
        record.text_body,
        record.is_customized,
        record.version,
    )


def _render_string(
    source: str, variables: dict[str, str], field: str, *, html: bool = False
) -> str:
    try:
        environment = _sandbox if html else _text_sandbox
        return environment.from_string(source).render(**variables)
    except Exception as exc:
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_RENDER_FAILED", f"{field} konnte nicht gerendert werden."
        ) from exc


async def render_email_template(
    session: AsyncSession | None,
    key: str,
    variables: dict[str, object],
    *,
    content_override: EmailTemplateContent | None = None,
) -> RenderedEmail:
    definition = template_definition(key)
    unknown = sorted(set(variables) - definition.allowed_variables)
    if unknown:
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_VARIABLE_NOT_ALLOWED",
            f"Die Variable {unknown[0]} ist für diese Vorlage nicht erlaubt.",
            variable=unknown[0],
        )
    safe_variables = {name: str(value) for name, value in variables.items()}
    content = content_override or await get_template_content(session, key)
    subject_source, html_source, text_source = validate_template_content(
        definition, content.subject, content.html_body, content.text_body
    )
    subject = _render_string(subject_source, safe_variables, "Der Betreff").strip()
    if "\r" in subject or "\n" in subject or len(subject) > SUBJECT_MAX_LENGTH:
        raise EmailTemplateValidationError(
            "EMAIL_TEMPLATE_SUBJECT_INVALID", "Der gerenderte Betreff ist ungültig."
        )
    body = sanitize_email_html(
        _render_string(html_source, safe_variables, "Der HTML-Inhalt", html=True)
    )
    context = global_email_context()
    html = _layout_env.get_template("base.html").render(content=Markup(body), **context)
    text_content = _render_string(text_source, safe_variables, "Der Text-Inhalt").rstrip()
    text = (
        f"{text_content}\n\n--\nOK Lab Flensburg · {context['site_name']}\n\n"
        f"Impressum:\n{context['imprint_url']}\n\nDatenschutz:\n{context['privacy_url']}"
    )
    return RenderedEmail(subject, html, text)


def render_pair(template: str, context: dict[str, object]) -> tuple[str, str]:
    """Default-Renderer für synchrone lokale Kompatibilitätstests."""
    aliases = {
        "link": "verification_url" if template == "verify_email" else "reset_url",
        "minutes": "expires_minutes",
        **({"message": "security_event_message"} if template == "mfa_security" else {}),
    }
    variables = {aliases.get(key, key): value for key, value in context.items() if key != "user"}
    if template == "mfa_security":
        variables.setdefault("security_event_title", "Sicherheitshinweis")
    rendered = asyncio.run(render_email_template(None, template, variables))
    return rendered.html, rendered.text


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
        logger.info("Console email prepared subject=%s body_bytes=%d", subject, len(text.encode()))
        return
    if settings.email_backend != "smtp":
        raise RuntimeError("Unsupported EMAIL_BACKEND")
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST must be configured for smtp email backend")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = Address(settings.smtp_from_name, addr_spec=settings.smtp_from_email)
    message["To"] = Address(to_name or "", addr_spec=to_email)
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


async def send_rendered_email(
    to_email: str,
    rendered: RenderedEmail,
    *,
    to_name: str | None = None,
    reply_to: str | None = None,
) -> None:
    await asyncio.to_thread(
        send_email,
        to_email,
        rendered.subject,
        rendered.html,
        rendered.text,
        to_name=to_name,
        reply_to=reply_to,
    )


def display_name(user: User) -> str:
    return (
        user.display_name
        or " ".join(part for part in [user.first_name, user.last_name] if part).strip()
        or user.email
    )


async def send_verification_email(session: AsyncSession, user: User, token: str) -> None:
    link = f"{get_settings().app_base_url.rstrip('/')}/email-bestaetigen?token={token}"
    rendered = await render_email_template(
        session, "verify_email", {"name": display_name(user), "verification_url": link}
    )
    await send_rendered_email(user.email, rendered)


async def send_password_reset_email(session: AsyncSession, user: User, token: str) -> None:
    settings = get_settings()
    link = f"{settings.app_base_url.rstrip('/')}/passwort-zuruecksetzen?token={token}"
    rendered = await render_email_template(
        session,
        "password_reset",
        {
            "name": display_name(user),
            "reset_url": link,
            "expires_minutes": settings.password_reset_expire_minutes,
        },
    )
    await send_rendered_email(user.email, rendered)


async def send_password_changed_email(session: AsyncSession, user: User) -> None:
    rendered = await render_email_template(
        session, "password_changed", {"name": display_name(user)}
    )
    await send_rendered_email(user.email, rendered)


async def send_welcome_email(session: AsyncSession, user: User) -> None:
    app_url = get_settings().app_base_url.rstrip("/")
    rendered = await render_email_template(
        session,
        "welcome",
        {
            "name": display_name(user),
            "app_url": app_url,
            "documentation_url": f"{app_url}/dokumentation",
            "profile_url": f"{app_url}/profil",
        },
    )
    await send_rendered_email(user.email, rendered, to_name=display_name(user))


_MFA_EVENTS = {
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


async def send_mfa_security_email(session: AsyncSession, user: User, event: str) -> None:
    title, message = _MFA_EVENTS[event]
    rendered = await render_email_template(
        session,
        "mfa_security",
        {
            "name": display_name(user),
            "security_event_title": title,
            "security_event_message": message,
        },
    )
    await send_rendered_email(user.email, rendered)


async def send_contact_notification(
    session: AsyncSession,
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
    rendered = await render_email_template(
        session,
        "contact_notification",
        {
            "name": name,
            "email": email,
            "subject": subject,
            "message": message,
            "received_at": received_at,
        },
    )
    await send_rendered_email(
        settings.contact_to_email,
        rendered,
        to_name=settings.contact_to_name,
        reply_to=email,
    )


async def send_contact_copy(
    session: AsyncSession, *, name: str, email: str, subject: str, message: str
) -> None:
    rendered = await render_email_template(
        session, "contact_copy", {"name": name, "subject": subject, "message": message}
    )
    await send_rendered_email(email, rendered, to_name=name)
