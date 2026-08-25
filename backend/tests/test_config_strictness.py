import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_unknown_environment_setting_remains_forbidden(tmp_path) -> None:
    env_file = tmp_path / "backend.env"
    env_file.write_text("STADTPLANER_UNKNOWN_DEPLOYMENT_SETTING=typo\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Settings(_env_file=env_file)


def test_enabled_modules_are_optional_and_comma_separated() -> None:
    assert Settings(_env_file=None).enabled_module_list == []
    settings = Settings(_env_file=None, enabled_modules="module-b, module-a")
    assert settings.enabled_module_list == ["module-b", "module-a"]
