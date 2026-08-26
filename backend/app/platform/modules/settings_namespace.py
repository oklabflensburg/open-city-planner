"""Gemeinsame, fachneutrale Environment-Namenskonvention für Module."""

import re

MODULE_ENV_PREFIX = "OCP_MODULE_"
_MODULE_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def module_id_to_env_prefix(module_id: str) -> str:
    """Leitet aus einer validen Kebab-Case-Modul-ID ein eindeutiges Präfix ab."""

    if not isinstance(module_id, str) or not _MODULE_ID.fullmatch(module_id):
        raise ValueError("Module IDs must be valid lowercase kebab-case identifiers.")
    return f"{MODULE_ENV_PREFIX}{module_id.upper().replace('-', '_')}_"


def is_module_environment_key(key: str) -> bool:
    return key.upper().startswith(MODULE_ENV_PREFIX)


__all__ = ["MODULE_ENV_PREFIX", "is_module_environment_key", "module_id_to_env_prefix"]
