"""AST-basierte Strukturregeln für modulübergreifende Python-Imports."""

import ast
from dataclasses import dataclass
from pathlib import Path

_ORM_IMPORT_PREFIXES = ("sqlalchemy", "sqlmodel")
_ORM_NAMES = frozenset(
    {"AsyncSession", "DeclarativeBase", "Mapped", "Session", "mapped_column", "relationship"}
)


@dataclass(frozen=True, slots=True)
class ModuleImportViolation:
    consumer_module: str
    source: Path
    imported_module: str
    allowed_alternative: str
    line: int

    def __str__(self) -> str:
        return (
            f'Module "{self.consumer_module}" imports forbidden foreign module '
            f'"{self.imported_module}" in {self.source}:{self.line}; import only the public '
            f'contract namespace "{self.allowed_alternative}".'
        )


@dataclass(frozen=True, slots=True)
class ContractPersistenceLeak:
    source: Path
    name: str
    line: int

    def __str__(self) -> str:
        return f'Public contract {self.source}:{self.line} leaks persistence type "{self.name}".'


@dataclass(frozen=True, slots=True)
class HostSettingsImportViolation:
    module_id: str
    source: Path
    imported_module: str
    line: int

    def __str__(self) -> str:
        return (
            f'Module "{self.module_id}" imports host settings "{self.imported_module}" '
            f"in {self.source}:{self.line}; use the module-scoped context.settings port."
        )


def find_cross_module_import_violations(
    modules_root: Path,
    *,
    package_prefix: str,
) -> tuple[ModuleImportViolation, ...]:
    """Erlaube von einem fremden Modul ausschließlich dessen contracts-Namespace."""

    prefix = tuple(package_prefix.split("."))
    violations: list[ModuleImportViolation] = []
    for source in sorted(modules_root.rglob("*.py")):
        relative = source.relative_to(modules_root)
        if len(relative.parts) < 2:
            continue
        consumer = relative.parts[0]
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        current_package = _current_package(prefix, relative)
        for node in ast.walk(tree):
            imported_names = _imported_names(node, current_package)
            forbidden_by_provider: dict[str, tuple[str, tuple[str, ...]]] = {}
            for imported in imported_names:
                parts = tuple(imported.split("."))
                if parts[: len(prefix)] != prefix or len(parts) <= len(prefix):
                    continue
                provider = parts[len(prefix)]
                if provider == consumer:
                    continue
                public_contract = (
                    len(parts) > len(prefix) + 1 and parts[len(prefix) + 1] == "contracts"
                )
                if public_contract:
                    continue
                current = forbidden_by_provider.get(provider)
                if current is None or len(parts) < len(current[1]):
                    forbidden_by_provider[provider] = (imported, parts)
            for provider, (imported, _) in forbidden_by_provider.items():
                violations.append(
                    ModuleImportViolation(
                        consumer_module=consumer,
                        source=source,
                        imported_module=imported,
                        allowed_alternative=".".join((*prefix, provider, "contracts")),
                        line=node.lineno,
                    )
                )
    return tuple(violations)


def find_contract_persistence_leaks(modules_root: Path) -> tuple[ContractPersistenceLeak, ...]:
    """Ermittelt ORM-/Session-Typen in allen öffentlichen contracts-Paketen."""

    leaks: list[ContractPersistenceLeak] = []
    for source in sorted(modules_root.rglob("*.py")):
        relative = source.relative_to(modules_root)
        if "contracts" not in relative.parts and source.stem != "contracts":
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(_ORM_IMPORT_PREFIXES):
                        leaks.append(ContractPersistenceLeak(source, alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(_ORM_IMPORT_PREFIXES):
                    leaks.append(ContractPersistenceLeak(source, node.module, node.lineno))
                    leaks.extend(
                        ContractPersistenceLeak(source, alias.name, node.lineno)
                        for alias in node.names
                        if alias.name in _ORM_NAMES
                    )
            elif isinstance(node, ast.Name) and node.id in _ORM_NAMES:
                leaks.append(ContractPersistenceLeak(source, node.id, node.lineno))
            elif isinstance(node, ast.Attribute) and node.attr in _ORM_NAMES:
                leaks.append(ContractPersistenceLeak(source, node.attr, node.lineno))
    return tuple(leaks)


def find_host_settings_import_violations(
    modules_root: Path,
) -> tuple[HostSettingsImportViolation, ...]:
    """Ermittelt direkte Host-Settings-Imports in modularen Python-Paketen."""

    violations: list[HostSettingsImportViolation] = []
    for source in sorted(modules_root.rglob("*.py")):
        relative = source.relative_to(modules_root)
        if len(relative.parts) < 2:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            imported: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported = (node.module,)
            for imported_module in imported:
                if imported_module == "app.core.config":
                    violations.append(
                        HostSettingsImportViolation(
                            module_id=relative.parts[0],
                            source=source,
                            imported_module=imported_module,
                            line=node.lineno,
                        )
                    )
    return tuple(violations)


def _current_package(prefix: tuple[str, ...], relative: Path) -> tuple[str, ...]:
    return (*prefix, *relative.parent.parts)


def _imported_names(node: ast.AST, current_package: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if not isinstance(node, ast.ImportFrom):
        return ()
    if node.level == 0:
        base = tuple(node.module.split(".")) if node.module else ()
    else:
        keep = len(current_package) - (node.level - 1)
        relative_base = current_package[: max(keep, 0)]
        suffix = tuple(node.module.split(".")) if node.module else ()
        base = (*relative_base, *suffix)
    if not base:
        return ()
    base_name = ".".join(base)
    imported_aliases = tuple(
        f"{base_name}.{alias.name}" for alias in node.names if alias.name != "*"
    )
    return (base_name, *imported_aliases)


__all__ = [
    "ContractPersistenceLeak",
    "HostSettingsImportViolation",
    "ModuleImportViolation",
    "find_contract_persistence_leaks",
    "find_cross_module_import_violations",
    "find_host_settings_import_violations",
]
