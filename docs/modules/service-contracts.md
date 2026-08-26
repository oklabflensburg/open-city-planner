# Cross-Module-Service-Contracts

Die Host-Registry stellt gezielte, typisierte Abfragen zwischen Backend-Modulen
bereit. Sie setzt die Ownership- und Importgrenzen aus
[ADR #92](../architecture/adr-modular-host-and-module-boundaries.md) um. Sie ist kein
allgemeiner Dependency-Injection-Container und kein versteckter Zugriff auf fremde
Interna.

## Service oder Domain Event?

Ein Service-Contract passt zu einer unmittelbaren Query oder Operation, deren
Ergebnis der Consumer für seinen aktuellen Ablauf benötigt. Ein Domain Event
beschreibt dagegen eine bereits eingetretene fachliche Tatsache und koppelt den
Producer nicht an einzelne Consumer. Queries wie „liefere Gebietszusammenfassungen“
verwenden einen Service; „Gebiet wurde veröffentlicht“ ist ein Event.

Service-Contracts sind standardmäßig asynchron. Damit können Implementierungen
später Datenbank- oder Netzwerkzugriffe ausführen, ohne den öffentlichen Contract zu
brechen. Ein Lookup selbst ist synchron und liefert die bereits registrierte,
runtime-skopierte Implementierung.

## Ownership und öffentlicher Contract

Der Provider besitzt Service-ID, Contract, DTOs und Implementierung. Nur sein
`contracts`-Namespace ist für fremde Module importierbar. DTOs sind unveränderliche
Werte ohne SQLAlchemy-Modelle, `Mapped`, `relationship`, `Session` oder Lazy-Loading.
Geometrien werden als GeoJSON-kompatible Mappings in EPSG:4326 mit der Reihenfolge
Längengrad/Breitengrad transportiert.

```python
# modules/analysis_areas/contracts.py
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.platform.modules.sdk import JsonValue

SERVICE_ID = "analysis-areas.query"
SERVICE_VERSION = 1


@dataclass(frozen=True, slots=True)
class AnalysisAreaSummary:
    area_id: str
    name: str
    geometry: Mapping[str, JsonValue]


class AnalysisAreaQueryService(Protocol):
    async def list_areas(self) -> Sequence[AnalysisAreaSummary]: ...
```

Service-IDs haben die Form `<owner-module>.<service-name>`. Der Host erzwingt, dass
ein Provider nur in seinem eigenen Namespace registriert. Service-Versionen sind
positive Integer und unabhängig von Manifest-, Host- und SDK-Version. Ein Contract
der Version 2 wird bei Bedarf parallel zu Version 1 unter derselben Service-ID
registriert; ein Lookup handelt Versionen nicht implizit aus.

## Registrierung und Lookup

Provider registrieren Implementierungen ausschließlich während
`module.register(context)`. Nach Abschluss aller `register()`-Hooks versiegelt die
Runtime die Registry. Spätere Registrierung oder ein Überschreiben derselben
Kombination aus ID und Version schlägt fehl.

```python
def register(self, context: ModuleContext) -> None:
    assert context.services is not None
    context.services.register(
        AnalysisAreaQueryService,
        SqlAnalysisAreaQueryService(context.database),
        service_id=SERVICE_ID,
        version=SERVICE_VERSION,
    )
```

Ein erforderlicher Lookup verwendet `require()`. Der Owner muss zugleich in
`manifest.requires.modules` des Consumers stehen. Die bestehende Dependency-Order
registriert den Provider zuerst. Ein fehlender Service, eine falsche exakte Version
oder ein anderer Contract-Typ stoppt die Runtime-Registrierung mit einem
strukturierten Fehler.

```python
from modules.analysis_areas.contracts import (
    SERVICE_ID,
    SERVICE_VERSION,
    AnalysisAreaQueryService,
)


def register(self, context: ModuleContext) -> None:
    assert context.services is not None
    self.areas = context.services.require(
        AnalysisAreaQueryService,
        service_id=SERVICE_ID,
        version=SERVICE_VERSION,
    )
```

`optional()` liefert bei einer vollständig fehlenden Service-ID `None`. Der Owner
muss als required oder optional Module Dependency deklariert sein. Existiert die ID
in einer anderen Version, wird dies als Inkompatibilität gemeldet und nicht wie ein
fehlendes optionales Feature behandelt.

## Versionierung und Deprecation

Eine Änderung an Methoden oder DTO-Semantik, die bestehende Consumer brechen kann,
erhält eine neue Service-Version und einen neuen öffentlichen Protocol-/DTO-Vertrag.
Versionen können während eines angekündigten Migrationszeitraums parallel laufen.
Die optionalen Registrierungsmetadaten `deprecated_since` und `replacement`
dokumentieren diesen Übergang; sie verändern Lookup oder Routing nicht. Erst nach
Migration aller Consumer darf die alte Version entfallen.

## Transaktionen und Lebensdauer

Registry und Implementierungen leben genau so lange wie die jeweilige
`ModuleRuntime`; es gibt keinen globalen Singleton. Die Registry eröffnet keine
Transaktion und reicht keine Session zwischen Modulen weiter. Ein Query-Service
öffnet über den eigenen Datenbank-Port seine eigene, hostverwaltete Transaktion und
liefert materialisierte DTOs zurück. Wenn mehrere fachliche Schreiboperationen eine
gemeinsame atomare Grenze benötigen, reicht ein einfacher Cross-Module-Service nicht
als implizite Transaktionskoordination; dieser Fall braucht einen ausdrücklich
entworfenen Application Contract. Query-first bleibt die bevorzugte Nutzung.

## Importgrenzen

Fremde Module dürfen ausschließlich `modules.<owner>.contracts` importieren. Imports
aus `.application`, `.domain`, `.integrations`, `.internal`, `.persistence` oder
`.repositories` sowie fremde ORM-Modelle sind verboten. Ein AST-basierter
Architekturtest prüft die Strukturregel ohne dateispezifische Allowlist und nennt im
Fehler Consumer, Quelldatei, problematischen Import sowie den erlaubten
`contracts`-Pfad.

Die Registry prüft stabile ID, Version, Ownership, Manifest-Abhängigkeit und exakte
Contract-Identität. Sie versucht bewusst keine vollständige Runtime-Introspection
von Python-Protocols; statische Typprüfung und Contract-Tests sichern deren fachliche
Methodensignaturen.
