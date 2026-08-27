from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.platform.modules import ModuleManifestError, parse_manifest
from app.platform.modules.trust import ModuleTrustClass, ModuleTrustGrant

ROOT = Path(__file__).resolve().parents[2]


def reviewed_grant(**overrides) -> ModuleTrustGrant:
    values = {
        "module_id": "community-module",
        "trust_class": ModuleTrustClass.REVIEWED_COMMUNITY,
        "source": "https://github.com/example/community-module",
        "module_version": "1.2.3",
        "package": "example-community-module",
        "package_version": "1.2.3",
        "commit": "a" * 40,
        "integrity": f"sha256:{'b' * 64}",
        "license": "AGPL-3.0-only",
        "reviewed_at": datetime(2026, 8, 27, tzinfo=UTC),
        "reviewed_by": "security-review@example.org",
    }
    values.update(overrides)
    return ModuleTrustGrant(**values)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("integrity", None, "require integrity"),
        ("commit", "short", "full lowercase Git SHAs"),
        ("source", "http://example.org/module", "absolute HTTPS URL"),
        (
            "reviewed_at",
            datetime(2026, 8, 27, tzinfo=UTC).replace(tzinfo=None),
            "include a timezone",
        ),
    ],
)
def test_reviewed_community_grant_requires_provenance_and_integrity(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        reviewed_grant(**{field: value})


def test_manifest_cannot_declare_its_own_trust_class() -> None:
    with pytest.raises(ModuleManifestError, match="trust_class"):
        parse_manifest(
            {
                "manifest_version": 1,
                "id": "community-module",
                "name": "Community module",
                "version": "1.2.3",
                "requires": {"host": ">=0.2.0,<1.0.0", "sdk": ">=1.0.0,<2.0.0"},
                "trust_class": "first-party",
            }
        )


def test_security_adr_states_real_process_boundaries_without_sandbox_claims() -> None:
    decision = (
        ROOT / "docs/architecture/adr-module-trust-model.md"
    ).read_text(encoding="utf-8")

    assert "In-process module == trusted code" in decision
    assert "Capability-/Permission-Enforcement ist keine OS- oder" in decision
    assert "Remote Integrations sind keine normalen In-Process-Module" in decision
    assert "erhalten keinen `ModuleContext`" in decision
    assert "checksums/provenance now, signing deferred" in decision
