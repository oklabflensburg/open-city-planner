from pathlib import Path

import pytest

from app.platform.modules.import_boundaries import (
    find_contract_persistence_leaks,
    find_cross_module_import_violations,
)

FIXTURES = Path(__file__).parent / "fixtures/service_modules"
PACKAGE = "tests.fixtures.service_modules"


def test_fixture_modules_import_foreign_code_only_through_contracts() -> None:
    assert find_cross_module_import_violations(FIXTURES, package_prefix=PACKAGE) == ()


def test_public_contract_dtos_do_not_leak_orm_or_session_types() -> None:
    assert find_contract_persistence_leaks(FIXTURES) == ()


@pytest.mark.parametrize(
    "foreign_package",
    ("application", "internal", "persistence", "repositories"),
)
def test_foreign_internal_imports_are_rejected_with_actionable_context(
    tmp_path: Path,
    foreign_package: str,
) -> None:
    modules = tmp_path / "modules"
    source = modules / "consumer" / "module.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        f"from example.modules.provider.{foreign_package} import Repository\n",
        encoding="utf-8",
    )

    violations = find_cross_module_import_violations(
        modules,
        package_prefix="example.modules",
    )

    assert len(violations) == 1
    violation = violations[0]
    assert violation.consumer_module == "consumer"
    assert violation.source == source
    assert violation.imported_module == f"example.modules.provider.{foreign_package}"
    assert violation.allowed_alternative == "example.modules.provider.contracts"
    assert "consumer" in str(violation)
    assert str(source) in str(violation)


def test_foreign_contract_import_is_allowed(tmp_path: Path) -> None:
    modules = tmp_path / "modules"
    source = modules / "consumer" / "module.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from example.modules.provider.contracts import QueryService\n",
        encoding="utf-8",
    )
    assert find_cross_module_import_violations(modules, package_prefix="example.modules") == ()


def test_foreign_module_import_from_package_root_is_rejected(tmp_path: Path) -> None:
    modules = tmp_path / "modules"
    source = modules / "consumer" / "module.py"
    source.parent.mkdir(parents=True)
    source.write_text("from example.modules import provider\n", encoding="utf-8")

    violations = find_cross_module_import_violations(
        modules,
        package_prefix="example.modules",
    )

    assert [violation.imported_module for violation in violations] == ["example.modules.provider"]


def test_contract_orm_import_is_rejected(tmp_path: Path) -> None:
    contracts = tmp_path / "modules/provider/contracts.py"
    contracts.parent.mkdir(parents=True)
    contracts.write_text("from sqlalchemy.orm import Mapped, relationship\n", encoding="utf-8")

    leaks = find_contract_persistence_leaks(tmp_path / "modules")

    assert {leak.name for leak in leaks} >= {"sqlalchemy.orm", "Mapped", "relationship"}
