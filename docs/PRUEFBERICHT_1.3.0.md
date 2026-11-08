# Lokaler Prüfbericht: Assist Router 1.3.0

Stand: 30.10.2026, Entwicklungsbranch `development/1.3.0`. Basis-Commit unverändert `5d641569aa2b0aa3dfac5613a59d23d9b884011f`. Kein Commit, Push, neuer Tag, Release oder produktiver HA-Eingriff.

## Ergebnis

- Vollständiger Lauf `pytest tests tests_live -q`: **281 bestanden, 1 Collection-Skip, keine Fehler**.
- Alle bisherigen Regressionen bleiben enthalten; Schema-/Versionsassertionen sind für den bewussten Schritt auf 1.3.0 / Config-Entry 3.2 angepasst.
- Ruff-Lint und Formatprüfung: erfolgreich, 36 Python-Dateien.
- Repository-/Versions-/HACS-Strukturprüfung: ohne Befund.
- Lokaler Secret-Scan: ohne Befund. Gitleaks wurde zusätzlich ausgeführt.
- Gepinnte HA-/Local-OpenAI-Quellen erneut gelesen und geprüft. Referenzen, beide JSON-Quellnachweise und `prompt_contracts.json` bleiben gegenüber der freigegebenen Basis bytegleich; Strict erhält keine neue Quellenfreigabe.
- Lokaler Paketbuilder validiert ZIP-CRC, Inhaltsmenge, Dateibytes und Ausschlüsse; keine Veröffentlichung.

Die JUnit-Datei liegt lokal unter `.package-tmp/test-results-1.3.0.xml` und ist vom Publikationsquellbaum ausgeschlossen.

## Neue Regressionen

Nachprüfung der beiden Sicherheitslücken: veraltete Optionswerte verdecken weder einen URL-Wechsel noch eine API-Key-Rotation; Optionswerte ersetzen keine fehlende Client-URL. Ein aktiver Weaviate-API-Key ist Bestandteil der Freigabe, auch bei veralteten Retrieval-Optionswerten. Unveränderte Verbindungsdaten sowie Modell-/Parameterwechsel bleiben freigegeben. Ein separater lokaler Test mit den Methoden aus dem gepinnten Local-OpenAI-1.14.0-Quellstand bestätigt Standard-Freigabe, Strict-`unknown_source` und die Blockaden ohne Provideraufruf.

Dauerhafte Freigabe nach JSON-/Settings-Neuladung; Integrationsreload mit neuen Objekten; geänderte Quellmethoden/Version ohne Standard-Quellzugriff; Modell- und Parameterwechsel; Thinking-Warnungen; unveränderter Gesprächskontext und Unicode bei Modellwechsel; Backend-/Credential-/Tenant-/Header-/Identitätswechsel; kanonische leere Defaults und äquivalente URLs bei weiterhin getrennten Proxy-Pfaden; Bestätigung und TOCTOU-Schutz im UI; Strict→Standard-Bestätigung; atomare 1.2.1-Migration inklusive ausgeschaltetem Prompt; keine erneute Migration aktueller Standard-Einträge; dynamische/unerlaubte Request-Overrides; entladene Agents mit sicherem Fallback; bestehende Blocked-Sperren nach Moduswechsel; datensparsame Werkzeugdiagnose ohne Argument-/Ergebniszugriff.

Die alten Tests für Strict, vollständige Fingerprint-Drift, native Intent-Vorverarbeitung, Delegation, Health-Caches, Priorität, Rückfragen, Busy/Blocked/Stale-Sperren, Lifecycle, keine Wiederholung unklarer Aktionen und Unicode-/Tool-Payload-Integrität laufen weiterhin mit.

## Nicht als grün behauptet

Die echte HA-Laufzeit wurde lokal nicht ausgeführt: verfügbar ist Python 3.12 auf Windows, keine passende Linux-/HA-2026.10.2-Umgebung. Der Collection-Skip ist kein bestandener HA-Test. Neun echte HA-Tests (beide Modi) sind für den Linux-CI-Job vorbereitet, der weiterhin einen zwingenden HA-Import-Guard besitzt.

Kein neuer GitHub-Lauf wurde ausgelöst. HACS und hassfest wurden nicht remote für diesen Arbeitsstand ausgeführt. Die frühere grüne 1.2.1-CI ist keine Freigabe von 1.3.0.

Local OpenAI 1.14.0 wird anhand seiner bekannten Konfigurationsstruktur und simulierten Integrationsupdates geprüft; es wurde kein produktiver Agent oder dessen SDK geladen. Tatsächlicher HA-Dialog, HA-Neustart-/Speicherübernahme, Provider-/Modellwirkung und Yuvomi-Berechtigungen bleiben isoliert abzunehmen. Standard ist explizites Vertrauen in die Integration, keine Garantie exklusiver Systemprompts.

Weiter: [Architektur und Grenzen](ARCHITEKTUR_1.3.0.md), [CI-Abnahmeplan](CI_ABNAHME_1.3.0.md).
