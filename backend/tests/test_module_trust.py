from pathlib import Path

import pytest

from app.platform.modules import ModuleManifestError, parse_manifest

ROOT = Path(__file__).resolve().parents[2]


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


def test_security_adr_keeps_trust_at_the_installation_boundary() -> None:
    decision = (ROOT / "docs/architecture/adr-module-trust-model.md").read_text(
        encoding="utf-8"
    )

    assert "In-process modules are trusted code" in decision
    assert "The module architecture is not a sandbox" in decision
    assert "Built-in / First-Party" in decision
    assert "Installed / Reviewed Third-Party" in decision
    assert "Remote / Untrusted" in decision
    assert "modules.lock" in decision
    assert "#173" in decision
    assert "#174" in decision
    assert "Discovery und Runtime bleiben klein" in decision


def test_community_review_documents_the_package_to_runtime_pipeline() -> None:
    review = (ROOT / "docs/modules/community-module-review.md").read_text(encoding="utf-8")

    stages = (
        "Package",
        "Installer",
        "Verify/Review",
        "modules.lock",
        "Backend/Frontend artifacts installed",
        "Discovery",
        "Runtime",
    )
    pipeline = review.split("```text", 1)[1].split("```", 1)[0]
    offsets = tuple(pipeline.index(stage) for stage in stages)
    assert offsets == tuple(sorted(offsets))
    assert "kein zweites Review-Gate" in review
    assert "Remote Integration" in review
