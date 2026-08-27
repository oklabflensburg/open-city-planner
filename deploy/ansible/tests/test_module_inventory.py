import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "deploy/ansible/scripts/validate_module_inventory.py"
SPEC = importlib.util.spec_from_file_location("validate_module_inventory", SCRIPT)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ModuleInventoryTest(unittest.TestCase):
    def validate(self, backend: str, frontend: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend_env = root / "backend.env"
            frontend_env = root / "frontend.env"
            backend_env.write_text(backend, encoding="utf-8")
            frontend_env.write_text(frontend, encoding="utf-8")
            VALIDATOR.validate_module_inventory(backend_env, frontend_env)

    def test_accepts_matching_versioned_inventory(self) -> None:
        self.validate(
            "ENABLED_MODULES=analysis-areas\n",
            "OCP_BACKEND_MODULES=analysis-areas@1.0.0\n",
        )

    def test_accepts_explicitly_disabled_modules(self) -> None:
        self.validate("ENABLED_MODULES=\n", "OCP_BACKEND_MODULES=\n")

    def test_rejects_frontend_inventory_without_runtime_module(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing from ENABLED_MODULES"):
            self.validate(
                "ENABLED_MODULES=\n",
                "OCP_BACKEND_MODULES=analysis-areas@1.0.0\n",
            )

    def test_rejects_runtime_module_missing_from_frontend_inventory(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing from OCP_BACKEND_MODULES"):
            self.validate(
                "ENABLED_MODULES=analysis-areas\n",
                "OCP_BACKEND_MODULES=\n",
            )

    def test_rejects_implicit_defaults(self) -> None:
        with self.assertRaisesRegex(ValueError, "ENABLED_MODULES is missing"):
            self.validate("APP_ENVIRONMENT=production\n", "OCP_BACKEND_MODULES=\n")


if __name__ == "__main__":
    unittest.main()
