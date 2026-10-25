# Entwicklung

Ziel: BugsDan/ha-assist-router. 1.2.1 bleibt erste öffentliche Funktionsbaseline mit einer ausdrücklich geprüften Bereinigung des alten privaten URL-Fallbacks. Keine Produktivdaten, Config-Entry-Exporte, Prompttexte, Zugangsdaten oder privaten Traces in Issues, Commits oder Testfixtures verwenden.

## Lokal prüfen

```sh
python -m venv .venv
# Environment aktivieren, dann:
python -m pip install -r requirements-test.txt
python tools/check_ha_api.py
python tools/check_prompt_compatibility.py
python tools/generate_prompt_contracts.py
python -m pytest tests tests_live -q
ruff check custom_components tests tests_live tools
ruff format --check custom_components tests tests_live tools
python tools/check_repository.py --tag v1.2.1
python tools/secret_scan.py
python tools/build_release.py
```

Python 3.12 reicht für Quellenvertrag-/Host-Tests. Echte HA-Laufzeittests benötigen Linux und Python >=3.14.2 mit homeassistant==2026.10.2. Ein lokaler Skip ist keine bestandene HA-Abnahme. Die Versions-/HACS-/hassfest-Prüfungen müssen später zusätzlich auf GitHub grün sein.

Die Originalgrafik wird mit `python tools/generate_brand.py` reproduziert; Pillow ist nur Entwicklungsabhängigkeit. SVG-Quellen unter assets/, PNGs unter custom_components/assist_router/brand/. Keine HA-Markenbestandteile übernehmen.

Quellenverträge nie blind aktualisieren. Diff, Original-Commit/Tag, Lizenz und Transportverhalten prüfen; geänderte erlaubte Quellen und Parameterpolitiken brauchen gezielte Tests. Der Baseline-Check erlaubt in dieser Vorbereitung nur den exakt gehashten Legacy-URL-Bereinigungspatch; alle anderen funktionalen Dateien bleiben bytegleich. Für spätere Funktionsreleases muss dessen Referenz nach bewusster Versions-/Codeprüfung fortgeschrieben werden, nicht bloss zur Beruhigung eines roten Tests.

## Commit und Release

Vor jedem Commit die **tatsächlich gestagten Dateien** mit `git diff --cached` prüfen. Nur den Inhalt des neuen Projektordners übernehmen, keine übergeordneten Codex-Dateien, .storage, .venv oder dist. Lokaler Gitleaks-Scan des Publikationsumfangs plus GitHub-Scan der gesamten Git-Historie ergänzen sich. Historische Secrets sind nicht durch Löschen einer aktuellen Datei bereinigt.

Die vorbereiteten Workflows besitzen nur contents:read und erzeugen keine Commits, Tags, Releases oder Deployments. Das erste öffentliche Repository, dessen Beschreibung/Topics und v1.2.1 dürfen erst nach gesonderter Freigabe angelegt werden. Siehe docs/GITHUB_HACS.md.
