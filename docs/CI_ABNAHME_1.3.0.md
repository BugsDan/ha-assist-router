# CI-Abnahme 1.3.0 — vorbereitet, noch nicht ausgelöst

Branch: `development/1.3.0`. Arbeitsstand ohne Commit/Push. Veröffentlichung und produktive HA-Installation sind nicht freigegeben. Nach gesonderter Freigabe lösen Pushes auf `development/1.3.0` dieselben Prüfungen wie `main` aus; Pull Requests und manueller Dispatch bleiben verfügbar.

## Lokale Prüfung

Mit Python 3.12 und `requirements-test.txt`:

```text
python tools/check_ha_api.py
python tools/check_prompt_compatibility.py
python tools/generate_prompt_contracts.py
python -m pytest tests tests_live -q
ruff check custom_components tests tests_live tools
ruff format --check custom_components tests tests_live tools
python tools/check_repository.py --tag v1.3.0
python tools/secret_scan.py
python tools/build_release.py
```

Der Tag-Parameter des Repository-Checks ist eine reine Versionsvalidierung; er erstellt keinen Tag. Referenzen, drei generierte JSON-Nachweise und die Strict-Verträge müssen gegenüber dem geprüften 1.2.1-Stand bytegleich bleiben. Der historische Publikations-Byteguard gilt für die absichtlich geänderten 1.3.0-Policy-/UI-Dateien nicht mehr; unveränderte Health-/Legacy-Migrationsdateien und Strict-Verträge bleiben geschützt. Die frühere Baseline-Datei wird nicht umgeschrieben.

## Verbindliche GitHub-Jobs nach gesonderter Commit-/Push-Freigabe

- `source-contracts`: gepinnte Quellen, strikter Generierungsvergleich, sämtliche Unit-/Regressionstests, Ruff, Repository- und Paketprüfung für 1.3.0.
- `actual-home-assistant`: Linux/Python 3.14 mit den exakten Anforderungen aus `requirements-test-ha.txt`. Der Import-Guard bleibt aktiv. Neun echte HA-Tests sind vorbereitet: Manifest-/Versionsprüfung sowie die bisherigen vier Kombinationen von Zusatzprompt und Fehlerfall jetzt in beiden Sicherheitsmodi.
- `hacs` und `hassfest`: unverändert, ohne Ignore-Ausnahmen oder Schreibrechte.
- `Secret scan`: Arbeitsbaum und volle Git-Historie mit Gitleaks sowie zusätzlicher lokaler Hygienescanner.

Bis diese Jobs am später freigegebenen Commit erfolgreich sind, gibt es keine neue grüne GitHub-Abnahme für 1.3.0. Eine grüne 1.2.1-CI gilt nicht für diesen Entwicklungsstand.

## Ergänzende manuelle Abnahme vor produktiver Nutzung

In isoliertem HA: 1.2.1-Config-Entry aktualisieren und Strict prüfen; bewussten Standard-Wechsel bestätigen; Agent freigeben und HA neu starten; Modell und Sampling ändern; unveränderte Freigabe überprüfen; Backend-Ziel ändern und Blockade plus explizite neue Bestätigung testen. Local OpenAI 1.14.0, OpenAI und Gemini separat prüfen. Health-Modellschlüssel unabhängig abgleichen.

Echte Werkzeugszenarien ausschließlich mit isolierter Testliste/Testgeräten: Yuvomi-Schreibschutz und Berechtigungsablehnung, erfolgreicher Aufruf, Fehler nach möglicher Ausführung und kein Replay. Die lokale Suite testet hierfür Host-/ChatLog-Verhalten ohne produktive MCP-Verbindung; sie ersetzt diese Abnahme nicht.
