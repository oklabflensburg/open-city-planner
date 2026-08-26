import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_module_architecture.py"
SPEC = importlib.util.spec_from_file_location("module_architecture_check", SCRIPT)
assert SPEC and SPEC.loader
architecture = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = architecture
SPEC.loader.exec_module(architecture)


def write_contract_files(root: Path, entries: list[dict[str, str]] | None = None) -> None:
    directory = root / "architecture"
    directory.mkdir(parents=True)
    (directory / "module-contract-rules.json").write_text(
        json.dumps({"version": 1, "rules": [{"id": "ARCH-BE-HOST-001"}]}),
        encoding="utf-8",
    )
    (directory / "module-boundary-baseline.json").write_text(
        json.dumps({"version": 1, "entries": entries or []}), encoding="utf-8"
    )


def test_repository_backend_boundaries_are_clean() -> None:
    assert architecture.active_violations(ROOT) == ()


def test_forbidden_host_import_is_reported_with_stable_rule(tmp_path: Path) -> None:
    write_contract_files(tmp_path)
    source = tmp_path / "backend/app/platform/modules/broken.py"
    source.parent.mkdir(parents=True)
    source.write_text("from app.services.users import UserService\n", encoding="utf-8")

    assert architecture.active_violations(tmp_path) == (
        architecture.Violation(
            "ARCH-BE-HOST-001",
            "backend/app/platform/modules/broken.py",
            "app.services.users",
            1,
        ),
    )


def test_module_private_host_and_foreign_internal_imports_are_reported(
    tmp_path: Path,
) -> None:
    write_contract_files(tmp_path)
    source = tmp_path / "backend/app/modules/alpha/application.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from app.db.session import AsyncSessionLocal\n"
        "from app.modules.beta.internal import secret\n",
        encoding="utf-8",
    )
    foreign = tmp_path / "backend/app/modules/beta/internal.py"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("secret = True\n", encoding="utf-8")

    violations = architecture.active_violations(tmp_path)

    assert any(item.rule == "ARCH-BE-PRIVATE-001" for item in violations)
    assert any(item.rule == "ARCH-BE-MODULE-001" for item in violations)


def test_exact_documented_baseline_exception_is_accepted(tmp_path: Path) -> None:
    source = tmp_path / "backend/app/platform/modules/legacy.py"
    source.parent.mkdir(parents=True)
    source.write_text("from app.services.legacy import LegacyService\n", encoding="utf-8")
    write_contract_files(
        tmp_path,
        [{
            "rule": "ARCH-BE-HOST-001",
            "source": "backend/app/platform/modules/legacy.py",
            "target": "app.services.legacy",
            "tracking_issue": "#999",
            "reason": "Temporary migration fixture.",
        }],
    )

    assert architecture.active_violations(tmp_path) == ()


def test_baseline_rejects_wildcards_and_missing_issue(tmp_path: Path) -> None:
    source = tmp_path / "backend/app/platform/modules/legacy.py"
    source.parent.mkdir(parents=True)
    source.write_text("# fixture\n", encoding="utf-8")
    write_contract_files(
        tmp_path,
        [{
            "rule": "ARCH-BE-HOST-001",
            "source": "backend/app/platform/modules/*.py",
            "target": "app.services.*",
            "tracking_issue": "later",
            "reason": "Too broad.",
        }],
    )

    with pytest.raises(ValueError, match="non-wildcard|tracking_issue"):
        architecture.load_baseline(tmp_path)
