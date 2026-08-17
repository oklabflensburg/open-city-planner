import uuid
from dataclasses import dataclass, field
from enum import StrEnum


class NotificationEventType(StrEnum):
    GIS_AREA_UPDATED = "GIS_AREA_UPDATED"
    GIS_AREA_DELETED = "GIS_AREA_DELETED"
    GIS_AREA_ADOPTED_FROM_OSM = "GIS_AREA_ADOPTED_FROM_OSM"
    GIS_AREA_STATUS_CHANGED = "GIS_AREA_STATUS_CHANGED"
    OSM_FEATURE_MAJOR_CHANGE = "OSM_FEATURE_MAJOR_CHANGE"
    AREA_STATISTICS_UPDATED = "AREA_STATISTICS_UPDATED"
    SOCIAL_PUBLICATION_PUBLISHED = "SOCIAL_PUBLICATION_PUBLISHED"
    SOCIAL_PUBLICATION_FAILED = "SOCIAL_PUBLICATION_FAILED"
    SOCIAL_PUBLICATION_APPROVAL_REQUIRED = "SOCIAL_PUBLICATION_APPROVAL_REQUIRED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REMOVED = "ROLE_REMOVED"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    ACCOUNT_REACTIVATED = "ACCOUNT_REACTIVATED"
    IMPORT_COMPLETED = "IMPORT_COMPLETED"
    IMPORT_FAILED = "IMPORT_FAILED"


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_type: NotificationEventType
    actor_user_id: uuid.UUID | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    resource_slug: str | None = None
    resource_title: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NotificationSpec:
    category: str
    priority: str
    title: str
    message: str
    action_url: str | None
    action_label: str | None
    dedupe_scope: str


class NotificationPolicy:
    """Maps domain events to neutral, recipient-safe user-facing content."""

    def render(self, event: DomainEvent) -> NotificationSpec:
        name = (event.resource_title or "Die Fläche").strip()[:160]
        polygon_url = f"/flaechen/{event.resource_slug}" if event.resource_slug else "/"
        role = str(event.metadata.get("role") or "Berechtigung")[:80]
        policies: dict[NotificationEventType, NotificationSpec] = {
            NotificationEventType.GIS_AREA_UPDATED: NotificationSpec(
                "GIS",
                "INFO",
                "Fläche aktualisiert",
                f"{name} wurde geändert.",
                polygon_url,
                "Fläche ansehen",
                "area-update",
            ),
            NotificationEventType.GIS_AREA_STATUS_CHANGED: NotificationSpec(
                "GIS",
                "INFO",
                "Flächenstatus geändert",
                f"Der Status von {name} wurde geändert.",
                polygon_url,
                "Fläche ansehen",
                "area-status",
            ),
            NotificationEventType.GIS_AREA_DELETED: NotificationSpec(
                "GIS",
                "WARNING",
                "Fläche gelöscht",
                "Eine von dir beobachtete oder verwaltete Fläche wurde gelöscht.",
                "/",
                "Karte öffnen",
                "area-delete",
            ),
            NotificationEventType.GIS_AREA_ADOPTED_FROM_OSM: NotificationSpec(
                "OSM",
                "SUCCESS",
                "Fläche übernommen",
                f"{name} wurde erfolgreich aus OpenStreetMap übernommen.",
                polygon_url,
                "Fläche ansehen",
                "osm-adoption",
            ),
            NotificationEventType.OSM_FEATURE_MAJOR_CHANGE: NotificationSpec(
                "OSM",
                "ACTION_REQUIRED",
                "OpenStreetMap-Daten geändert",
                f"Die OSM-Quelle zu {name} hat sich wesentlich geändert.",
                polygon_url,
                "Änderungen prüfen",
                "osm-major-change",
            ),
            NotificationEventType.AREA_STATISTICS_UPDATED: NotificationSpec(
                "DATA",
                "INFO",
                "Gebietsdaten aktualisiert",
                f"Für {name} sind neue Statistikdaten verfügbar.",
                f"/gebiete/{event.resource_slug}" if event.resource_slug else "/gebiete",
                "Gebiet ansehen",
                "area-statistics",
            ),
            NotificationEventType.SOCIAL_PUBLICATION_PUBLISHED: NotificationSpec(
                "SOCIAL",
                "SUCCESS",
                "Social-Post veröffentlicht",
                "Eine Veröffentlichung wurde erfolgreich publiziert.",
                "/admin/social",
                "Veröffentlichungen öffnen",
                "social-published",
            ),
            NotificationEventType.SOCIAL_PUBLICATION_FAILED: NotificationSpec(
                "SOCIAL",
                "ERROR",
                "Social-Veröffentlichung fehlgeschlagen",
                "Eine Veröffentlichung konnte nicht gesendet werden.",
                "/admin/social",
                "Fehler prüfen",
                "social-failed",
            ),
            NotificationEventType.SOCIAL_PUBLICATION_APPROVAL_REQUIRED: NotificationSpec(
                "SOCIAL",
                "ACTION_REQUIRED",
                "Social-Post wartet auf Freigabe",
                "Eine vorbereitete Veröffentlichung muss geprüft werden.",
                "/admin/social",
                "Jetzt prüfen",
                "social-approval",
            ),
            NotificationEventType.ROLE_ASSIGNED: NotificationSpec(
                "ACCOUNT",
                "INFO",
                "Rolle vergeben",
                f"Dir wurde die Rolle {role} zugewiesen.",
                "/profil/sicherheit",
                "Sicherheit öffnen",
                "role-assigned",
            ),
            NotificationEventType.ROLE_REMOVED: NotificationSpec(
                "ACCOUNT",
                "WARNING",
                "Rolle entfernt",
                f"Die Rolle {role} wurde deinem Konto entzogen.",
                "/profil/sicherheit",
                "Sicherheit öffnen",
                "role-removed",
            ),
            NotificationEventType.ACCOUNT_DEACTIVATED: NotificationSpec(
                "ACCOUNT",
                "WARNING",
                "Konto deaktiviert",
                "Dein Konto wurde durch die Administration deaktiviert.",
                "/login",
                "Zur Anmeldung",
                "account-deactivated",
            ),
            NotificationEventType.ACCOUNT_REACTIVATED: NotificationSpec(
                "ACCOUNT",
                "SUCCESS",
                "Konto reaktiviert",
                "Dein Konto wurde wieder aktiviert.",
                "/profil",
                "Profil öffnen",
                "account-reactivated",
            ),
            NotificationEventType.IMPORT_COMPLETED: NotificationSpec(
                "SYSTEM",
                "SUCCESS",
                "Import abgeschlossen",
                f"Der Import {name} wurde abgeschlossen.",
                None,
                None,
                "import-completed",
            ),
            NotificationEventType.IMPORT_FAILED: NotificationSpec(
                "SYSTEM",
                "ERROR",
                "Import fehlgeschlagen",
                f"Der Import {name} konnte nicht abgeschlossen werden.",
                None,
                None,
                "import-failed",
            ),
        }
        return policies[event.event_type]


notification_policy = NotificationPolicy()
