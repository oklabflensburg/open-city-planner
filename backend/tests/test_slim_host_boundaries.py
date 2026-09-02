import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = ROOT / "backend/app"

FORBIDDEN_RUNTIME_PREFIXES = (
    "app.api.analytics",
    "app.api.assistant",
    "app.api.data_sources",
    "app.api.search",
    "app.services.analytics",
    "app.services.area_statistics",
    "app.services.assistant",
    "app.services.comparables",
    "app.services.flensburg_statistics_import",
    "app.services.flensburg_superset",
    "app.services.location_analytics",
    "app.services.search_",
    "app.services.social_",
    "app.services.wikidata_enrichment",
)

REMOVED_RUNTIME_PATHS = (
    "api/analytics.py",
    "api/assistant.py",
    "api/data_sources.py",
    "api/search.py",
    "modules/analysis_areas",
    "services/area_statistics.py",
    "services/assistant.py",
    "services/social_publishing.py",
    "services/wikidata_enrichment.py",
)


def imported_modules(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            result.append((node.module, node.lineno))
        elif isinstance(node, ast.Import):
            result.extend((alias.name, node.lineno) for alias in node.names)
    return result


def test_removed_domains_cannot_reenter_backend_runtime() -> None:
    violations: list[str] = []
    for path in BACKEND_APP.rglob("*.py"):
        relative = path.relative_to(BACKEND_APP)
        if relative.parts[:2] == ("platform", "modules"):
            continue
        for imported, line in imported_modules(path):
            if imported.startswith(FORBIDDEN_RUNTIME_PREFIXES):
                violations.append(f"{relative}:{line}: {imported}")
    assert violations == []


def test_removed_domain_runtime_paths_stay_absent() -> None:
    assert [path for path in REMOVED_RUNTIME_PATHS if (BACKEND_APP / path).exists()] == []


def test_notifications_remain_a_host_capability() -> None:
    router = (BACKEND_APP / "api/router.py").read_text(encoding="utf-8")
    assert "notifications_router" in router
    assert (BACKEND_APP / "services/notifications.py").is_file()
    assert (BACKEND_APP / "models/notification.py").is_file()
