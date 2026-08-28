# Reproduzierbare Supply Chain

Dieses Repository behandelt Lockfiles, Toolversionen, Action-SHAs und
Container-Digests als Teil eines Releases. Derselbe Commit verwendet in CI und
Produktion Python 3.12.14, uv 0.12.5 und dieselben transitiven Pakete aus
`backend/uv.lock`. Node.js 22.23.2, pnpm 11.22.0 und Ansible Core 2.19.12 sind
ebenfalls festgelegt. Die transitiven Abhängigkeiten des Ansible-Controllers sind
mit Paket-Hashes in `deploy/ansible/requirements.txt` fixiert.

## Backend-Abhängigkeiten aktualisieren

Direkte Anforderungen bleiben in `backend/pyproject.toml`, transitive Versionen
in `backend/uv.lock`. uv muss die dort festgelegte Version besitzen:

```bash
python3 -m pip install 'uv==0.12.5'
cd backend
uv lock --upgrade
uv sync --frozen --extra dev
uv lock --check
```

Eine einzelne Abhängigkeit wird kontrolliert aktualisiert:

```bash
cd backend
uv lock --upgrade-package fastapi
uv sync --frozen --extra dev
```

`pyproject.toml` und `uv.lock` gehören in denselben Pull Request. CI führt
`uv lock --check` aus und lehnt einen veralteten Lock ab. Produktion verwendet
`uv sync --frozen --no-dev --no-editable`; sie löst keine Versionen neu auf.

## Frontend-Abhängigkeiten aktualisieren

Die exakte pnpm-Version steht in `frontend/package.json`. Nach einer bewussten
Änderung werden Manifest und Lockfile gemeinsam geprüft:

```bash
cd frontend
pnpm update <paket>
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm build
```

## Ansible aktualisieren

Die direkte Version steht in `deploy/ansible/requirements.in`; das generierte
`requirements.txt` pinnt alle transitiven Pakete samt Hashes:

```bash
cd deploy/ansible
uv pip compile requirements.in --universal --generate-hashes --output-file requirements.txt
python -m pip install --require-hashes --requirement requirements.txt
python -m unittest discover -s tests
ansible-playbook --syntax-check playbooks/deploy.yml
```

## GitHub Actions aktualisieren

Externe Actions dürfen ausschließlich vollständige 40-stellige Commit-SHAs
verwenden. Für ein Update:

1. offizielles Upstream-Release auswählen;
2. Tag und Commit im Upstream-Repository verifizieren;
3. Full SHA im Workflow eintragen;
4. lesbaren Versionskommentar wie `# v6.1.0` beibehalten;
5. die Zuordnung von Versionskommentar und SHA online prüfen;
6. die lokalen Policy-Tests und das vollständige Release Gate ausführen.

```bash
python scripts/verify-supply-chain.py --verify-action-refs
python -m unittest scripts.tests.test_verify_supply_chain
```

Ohne `--verify-action-refs` arbeitet der Validator rein lokal und erzwingt Full
SHAs, exakte Versionskommentare und die Ablehnung von Null-SHAs.
Die optionale Online-Prüfung löst jeden kommentierten Tag über die GitHub API
auf, folgt dabei auch annotierten Tags und vergleicht den resultierenden Commit
mit dem Workflow-Pin. Sie ist bewusst kein Netzwerkzugriff in jedem normalen
Build, sondern ein verpflichtender Review-Schritt für Action-Update-PRs.

Major-Tags wie `@v6` sind nicht zulässig.

## Container aktualisieren

Der lesbare Image-Tag bleibt zusammen mit dem Manifest-Digest erhalten:

```bash
docker buildx imagetools inspect postgis/postgis:16-3.5
```

Alle Workflow-Stellen müssen denselben Wert der Form
`postgis/postgis:16-3.5@sha256:…` verwenden. Nach einem Update sind Migrationen
gegen eine frische Datenbank und E2E vollständig auszuführen.

## Automatisierte Updates

`.github/dependabot.yml` erzeugt wöchentlich gruppierte Pull Requests für GitHub
Actions, Python/uv und npm/pnpm. Es gibt keine direkten Dependency-Commits auf
`main`; die Pull Requests durchlaufen Backend, Frontend, E2E, Security,
Supply-Chain und Release Gate.

Dependabot erhält die vollständigen Action-SHA-Pins. Bei jedem GitHub-Actions-PR
muss im Review zusätzlich geprüft werden, dass Dependabot auch den lesbaren
Versionskommentar aktualisiert hat. Vor dem Merge ist deshalb
`python scripts/verify-supply-chain.py --verify-action-refs` auszuführen; ein
veralteter Kommentar lässt diese Prüfung fehlschlagen.

## SBOM und Provenance

Das Release Gate erzeugt mit Syft 1.51.0 zwei transitive CycloneDX-JSON-Dateien:

- `backend-sbom.cdx.json`
- `frontend-sbom.cdx.json`

Sie werden 90 Tage als gemeinsames Workflow-Artefakt gespeichert. Ein Fehler bei
der Erzeugung blockiert das Release Gate und damit das Deployment. Bei Pushes auf
`main` erzeugt GitHub Artifact Attestations zusätzlich eine Build-Provenance für
beide SBOM-Dateien. Dafür benötigt der Workflow `id-token: write` und
`attestations: write`.

Separat verteilte Module werden als [`.ocp` Package Bundle v1](modules/package-bundle.md)
veröffentlicht. SHA-256 über die vollständigen Bundle-Bytes ist der immutable
Release-Digest und wird in `modules.lock` übernommen. `module.yaml` kann Referenzen
auf SBOM und Build-Attestation transportieren; eine spätere Registry (#175)
indexiert Bundle-Digest und Provenance, ohne einen neuen Trust-Grant zu erzeugen.
Wo eine Modul-Releasepipeline Attestations erzeugt, soll sie den Bundle-Digest mit
der zugehörigen SBOM über `actions/attest-sbom` binden.

### Reviewed Community Modules

Ein Community-Modul darf nur mit exakter Modul-, Distribution- und Dependency-
Version, gelocktem Abhängigkeitssatz, sichtbarer Lizenz, SBOM, vollständigem
Commit-SHA und SHA-256-Integrität in-process aktiviert werden. Dependency Audit,
Dependency Review, CodeQL/SAST und Secret Scan sind verpflichtend und folgen
derselben High-/Critical-Policy wie der Host. Unbekannte Integrität oder eine
kompromittierte Quelle blockiert Installation und Update.

Eine eigene Signatur-PKI wird erst bewertet, wenn separate Modul-Artefakte und ein
realer Distributionskanal existieren. Bis dahin gilt: checksums/provenance now,
signing deferred. Siehe
[Modul-Trust-ADR](architecture/adr-module-trust-model.md). Der
[Installer mit `modules.lock`](modules/installer.md) prüft lokale `.ocp`-Artefakte
vor der Installation. Discovery und Runtime implementieren keine parallele
Integritätsprüfung.

## Kontrolliertes Notfallupdate

Auch ein Emergency-Patch erfolgt auf einem Branch: betroffenen Pin ändern,
Lockfile beziehungsweise Digest aktualisieren, vollständiges Release Gate
ausführen, Review einholen und erst danach mergen. Keine Pakete werden ad hoc auf
dem Produktionsserver aktualisiert. Der Deploy referenziert den geprüften
Commit-SHA; Backup, Migration, atomarer `current`-Symlink, Smoke Tests und
Rollback bleiben unverändert.

## Lokale Policy-Prüfung

```bash
python scripts/verify-supply-chain.py
python scripts/verify-supply-chain.py --verify-action-refs
python -m unittest scripts.tests.test_verify_supply_chain
```

Die Regressionstests beweisen insbesondere, dass Action-Major-Tags, Null-SHAs,
fehlende Versionskommentare, Tag/SHA-Abweichungen,
undigestierte Images, Ansible-Versionsbereiche und ein veraltetes uv-Lockfile
abgelehnt werden.
