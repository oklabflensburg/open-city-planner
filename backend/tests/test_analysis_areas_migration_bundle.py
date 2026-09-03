from pathlib import Path

from app.platform.modules.bundle import staged_ocp_bundle
from app.platform.modules.installer import read_modules_lock
from tests.fixtures.build_analysis_areas_migration_bundle import MIGRATION_ROOT, build_bundle
from tests.test_module_installer import _installer


def test_passive_analysis_areas_migration_bundle_is_deterministic_and_installable(
    tmp_path: Path,
) -> None:
    source_commit = "a" * 40
    first = tmp_path / "first.ocp"
    second = tmp_path / "second.ocp"

    assert build_bundle(first, source_commit=source_commit) == build_bundle(
        second, source_commit=source_commit
    )
    assert first.read_bytes() == second.read_bytes()

    installer = _installer(tmp_path / "modules")
    with staged_ocp_bundle(first) as (package_root, package):
        assert package.module_id == "analysis-areas"
        assert package.version == "0.0.0"
        assert package.frontend is None
        installed = installer.install(package_root)

    assert installed.enabled is False
    assert read_modules_lock(installer.lock_path).modules == (installed,)
    installed_history = (
        installer.root
        / "installed/analysis-areas/0.0.0/backend/site-packages"
        / "ocp_module_analysis_areas/migrations/history"
    )
    assert {path.name for path in installed_history.glob("2026*.py")} == {
        path.name for path in MIGRATION_ROOT.glob("*.py")
    }
    for source in MIGRATION_ROOT.glob("*.py"):
        assert (installed_history / source.name).read_bytes() == source.read_bytes()
