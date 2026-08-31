import io
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit

from PIL import Image, ImageOps

from app.core.config import Settings
from app.models.social_publication import SocialPublicationOutbox, SocialPublishingSettings
from app.models.user_polygon import UserPolygon
from app.services.social_policy import VIEWPORTS


class ScreenshotError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class ScreenshotTarget:
    url: str
    alt_text: str


@dataclass(frozen=True, slots=True)
class AreaScreenshotResource:
    uuid: uuid.UUID
    slug: str
    name: str
    area_type: str


def screenshot_target(
    event: SocialPublicationOutbox,
    resource: AreaScreenshotResource | UserPolygon | None,
    env: Settings,
    policy: SocialPublishingSettings,
) -> ScreenshotTarget:
    base = env.app_base_url.rstrip("/")
    if event.resource_type == "ANALYSIS_AREA":
        if not isinstance(resource, AreaScreenshotResource):
            raise ScreenshotError("Die öffentliche Gebietsseite existiert nicht mehr.", retryable=False)
        path = f"/gebiete/{resource.slug}"
        type_label = {
            "MUNICIPALITY": "Gemeinde",
            "DISTRICT": "Stadtteil",
            "QUARTER": "Quartier",
        }.get(resource.area_type, "Gebiet")
        alt = (
            f"Screenshot der öffentlichen Stadtplaner-Gebietsseite „{resource.name}“ in "
            f"Flensburg mit Karte des {type_label.lower()}s und öffentlichen Kennzahlen."
        )
    elif event.resource_type == "USER_POLYGON":
        if not isinstance(resource, UserPolygon):
            raise ScreenshotError("Die öffentliche Flächenseite existiert nicht mehr.", retryable=False)
        if policy.polygon_osm_adoption_link_target == "GIS":
            path = "/"
            polygon_query = str(resource.uuid)
            alt = (
                f"Kartenausschnitt des Stadtplaners mit der ausgewählten, aus OpenStreetMap "
                f"übernommenen Fläche „{resource.name}“ in Flensburg."
            )
        else:
            path = f"/flaechen/{resource.slug}"
            polygon_query = None
            alt = (
                f"Screenshot der öffentlichen Stadtplaner-Flächenseite „{resource.name}“ "
                f"in Flensburg mit Lage, Kategorie und öffentlichen Flächendaten."
            )
    elif event.resource_type == "ANALYSIS_AREA_COLLECTION":
        path = "/gebiete"
        alt = (
            "Screenshot der öffentlichen Stadtplaner-Gebietsübersicht für Flensburg mit "
            "Gemeinde, Stadtteilen und Quartieren."
        )
    else:
        raise ScreenshotError("Für diesen Eventtyp ist kein Screenshot-Ziel freigegeben.", retryable=False)
    query_values = {
        "social-preview": "1",
        "map": int(policy.screenshot_show_map),
        "facts": int(policy.screenshot_show_facts),
        "pois": int(policy.screenshot_show_pois),
        "branding": int(policy.screenshot_show_branding),
    }
    if event.resource_type == "USER_POLYGON" and polygon_query:
        query_values["polygon"] = polygon_query
    query = urlencode(query_values)
    return ScreenshotTarget(url=f"{base}{path}?{query}", alt_text=alt[:1500])


class ScreenshotService:
    """Renders allowlisted public Stadtplaner routes without authentication."""

    def __init__(self, env: Settings) -> None:
        self.env = env
        self.root = Path(env.mastodon_screenshot_directory).resolve()

    def validate_url(self, url: str) -> None:
        expected = urlsplit(self.env.app_base_url.rstrip("/"))
        candidate = urlsplit(url)
        if (
            candidate.scheme not in {"http", "https"}
            or (candidate.scheme, candidate.netloc) != (expected.scheme, expected.netloc)
            or not (
                candidate.path in {"/", "/gebiete"}
                or candidate.path.startswith("/gebiete/")
                or candidate.path.startswith("/flaechen/")
            )
            or candidate.username
            or candidate.password
        ):
            raise ScreenshotError("Screenshot-Ziel ist nicht freigegeben.", retryable=False)
        normalized = urlunsplit((candidate.scheme, candidate.netloc, candidate.path, candidate.query, ""))
        if normalized != url:
            raise ScreenshotError("Screenshot-Ziel enthält nicht erlaubte URL-Bestandteile.", retryable=False)

    async def capture(self, event_id: uuid.UUID, target_url: str, viewport: str) -> str:
        self.validate_url(target_url)
        width, height = VIEWPORTS[viewport]
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        output = (self.root / f"{event_id}.jpg").resolve()
        if output.parent != self.root:
            raise ScreenshotError("Ungültiger Screenshot-Pfad.", retryable=False)
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ScreenshotError("Playwright ist auf dem Publisher nicht installiert.", retryable=False) from exc
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": width, "height": height},
                    locale="de-DE",
                    reduced_motion="reduce",
                )
                page = await context.new_page()
                response = await page.goto(
                    target_url,
                    wait_until="domcontentloaded",
                    timeout=self.env.mastodon_screenshot_timeout_seconds * 1000,
                )
                if response is None:
                    raise ScreenshotError("Öffentliche Vorschau lieferte keine Antwort.", retryable=True)
                if response.status == 404:
                    raise ScreenshotError("Öffentliche Vorschauseite wurde nicht gefunden.", retryable=False)
                if response.status >= 500:
                    raise ScreenshotError("Öffentliche Vorschauseite ist vorübergehend nicht verfügbar.", retryable=True)
                self.validate_url(page.url)
                ready = page.locator('[data-social-preview-ready="true"]')
                await ready.wait_for(
                    state="visible",
                    timeout=self.env.mastodon_screenshot_timeout_seconds * 1000,
                )
                raw = await page.locator("[data-social-preview-capture]").screenshot(type="png")
                await browser.close()
        except PlaywrightTimeoutError as exc:
            raise ScreenshotError("Öffentliche Vorschau wurde nicht rechtzeitig bereit.", retryable=True) from exc
        except ScreenshotError:
            raise
        except Exception as exc:
            raise ScreenshotError("Chromium konnte die öffentliche Vorschau nicht rendern.", retryable=True) from exc
        with Image.open(io.BytesIO(raw)) as image:
            rendered = ImageOps.pad(image.convert("RGB"), (width, height), color="white")
            rendered.save(output, "JPEG", quality=88, optimize=True)
        os.chmod(output, 0o600)
        return str(output)

    def read(self, path: str) -> bytes:
        resolved = Path(path).resolve()
        if resolved.parent != self.root or not resolved.is_file():
            raise FileNotFoundError(path)
        return resolved.read_bytes()

    def remove(self, path: str | None) -> None:
        if not path:
            return
        resolved = Path(path).resolve()
        if resolved.parent == self.root:
            resolved.unlink(missing_ok=True)
