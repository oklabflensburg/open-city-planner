import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_external_module_imports.py"
SPEC = importlib.util.spec_from_file_location("external_import_check", SCRIPT)
assert SPEC and SPEC.loader
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


def test_external_module_may_import_only_public_sdk(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text(
        "from app.platform.modules.sdk import ModuleContext\n",
        encoding="utf-8",
    )

    assert checker.private_host_imports(tmp_path) == ()


def test_external_module_private_host_import_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "legacy.py"
    source.write_text(
        "from app.models.user_polygon import UserPolygon\n"
        "from app.services.polygon_analytics import counts\n",
        encoding="utf-8",
    )

    assert [(item.imported, item.line) for item in checker.private_host_imports(tmp_path)] == [
        ("app.models.user_polygon", 1),
        ("app.services.polygon_analytics", 2),
    ]
