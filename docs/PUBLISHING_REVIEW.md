# Review: bereinigte Assist-Router-Publikation 1.2.1

Stand: 25.10.2026. Ziel **BugsDan/ha-assist-router**. Ausschliesslich lokal vorbereitet: kein Repository, Commit, Tag, Release oder Brands-PR erstellt, nichts veröffentlicht und keine produktive HA-Installation verändert. Version **1.2.1** und Config-Entry-Schema **3.1** bleiben erhalten.

## Bereinigung abgeschlossen

Die historische private Default-URL ist aus `custom_components/assist_router/migration.py` entfernt. Die alte 1.0-Migration verwendet jetzt ausschliesslich einen **explizit gespeicherten gültigen** `models_url`-Wert. Sie erfindet keinen Host, leitet keine Credentials um und deaktiviert keine Health-Prüfung.

Ist ein 1.0-Wert fehlend oder ungültig, wird die Migration **atomar ohne Schreibzugriff abgewiesen**. Dieser seltene Legacy-Sonderfall muss vor dem Upgrade mit dem gesicherten bisherigen Code im vorhandenen Konfigurationsdialog ausdrücklich vervollständigt werden. Eine nicht gespeicherte Adresse lässt sich nicht gleichzeitig entfernen und ohne Zusatzinformation zuverlässig rekonstruieren. Kein .storage-Eingriff und kein Löschen/Neuanlegen des Config Entry als Umgehung. Details: [HACS-Übergang](GITHUB_HACS.md).

Die einzige funktionale Änderung ist das Entfernen dieses Fallback-Arguments. Ein lokaler AST-Vergleich gegen die bisherige 1.2.1-Migration belegt die Gleichheit nach genau dieser Entfernung. Originalhash, genehmigter Bereinigungshash und AST-Hash stehen nachvollziehbar in baseline-1.2.1.json; der Baseline-Check erlaubt keine weiteren Laufzeitänderungen. Die übrigen 15 funktionalen Component-Dateien einschliesslich Promptlogik, Quellenverträgen und Übersetzungen bleiben bytegleich; am Manifest sind weiterhin nur Maintainer-/Repositorylinks ergänzt.

## Kompatibilität und Prüfungen

- **Aktuelle 1.2.x-/Schema-3.1-Einträge:** keine Änderung an Daten oder Optionen und kein Migrationsschreibzugriff. Zentraler Systemprompt, Agent-Ergänzungen, Reihenfolge, Aktivierung, gespeicherte Freigaben und Health-Einstellungen bleiben identisch. Gleichheit von Options-Fingerprint und Promptrevision vor/nach Migration getestet.
- **1.1-/Schema-2-Einträge:** bestehende Normalisierung/Migration unverändert; komplette kanonische Health-Objekte, Reihenfolge und deaktivierte Agents erhalten. Neue Promptverwaltung bleibt beim Upgrade wie bisher standardmässig aus.
- **1.0 mit gespeicherter URL:** exakte Übernahme auch privater LAN-/Proxy-Endpunkte. Credential-, Modell-/Instanz- und Zeitbudgeterhalt sowie Vorrang der Optionen getestet. Die neue Publikationsregel für private URL-Literale ist nur ein Quellcode-Hygienecheck; sie verbietet keine bestehenden privaten Laufzeitendpunkte.
- **1.0 ohne gültige URL:** Rückgabe False, kein Update-Aufruf und alter Entry vollständig unverändert. Kein stiller Cloud-Fallback oder Testaufruf am Modellserver.
- **240 Tests bestanden, 1 echte HA-Sammlung übersprungen**, keine Fehler/Fehlschläge. Zehn neue Kompatibilitäts-/Abbruchfälle ergänzen die bisherige gesamte Regression. JUnit-Dauer: 31.059 Sekunden. Ergebnisse: publication-test-results.xml und publication-validation.json.
- Quellen-/API-Verträge und Prompt-Allowlist erneut ohne Drift reproduziert; Lint, Format und Kompilierung bestanden. Alle No-Retry-, Busy-/Blocked-, Rückfrage-, Unicode- und Toolargument-Regeln bleiben erhalten.
- **Secret-Scan:** Gitleaks v8.30.1 mit Standardregeln und Redaction auf dem vollständigen kuratierten Publikationsumfang; keine pauschalen Test-/Referenz-Ausnahmen. Zusätzlicher Hygienecheck prüft nun auch fest codierte private Endpoint-URLs. Finale Ergebnisse in publication-validation.json. Scannerherkunft/Upstream-Prüfsumme: secret-scanner-provenance.json.

## HACS-Verwaltung ohne Konfigurationsverlust

Vollständiges HA-Backup erstellen, bisherigen Code ausserhalb custom_components sichern und laufende/unklare Aktionen am tatsächlichen Ziel prüfen. Nach späterer Veröffentlichung dieselbe Integration **1.2.1** über HACS erneut herunterladen, denselben Config Entry und Codepfad behalten, HA neu starten und vorhandene Optionen/IDs prüfen. Keine neue Integration anlegen und keine .storage-Dateien löschen oder manuell editieren. HACS verwaltet den Code, nicht die Routeroptionen.

Nach dem Neustart neue Conversations verwenden. Das RAM-Safety-Ledger und ChatLogs werden nicht persistent migriert; der Neustart ist kein sicherer Retry einer unklaren Aktion. Bei unabhängig geänderten Ziel-Agent-Prompts bleibt eine erneute Kompatibilitätsprüfung erforderlich; der HACS-Wechsel selbst erzwingt keine Änderung gespeicherter Freigaben.

## Noch vor einer späteren Veröffentlichung nötig

Echte Linux-HA-Tests, offizielle HACS-/hassfest-Checks und Ziel-HA-/HACS-Übernahme sind nicht lokal ausgeführt. Docker/geeignete Linux-HA-Laufzeit fehlen hier. Die vorbereiteten GitHub-Workflows bleiben lesend und wurden nicht ausgelöst. Erst nach gesonderter Freigabe Repository/Settings anlegen und diese Checks grün abwarten. Ein lokaler Skip ist kein bestandener HA-Lauf.

Originale lokale SVG-/PNG-Brand-Assets, MIT für eigene Dateien mit separaten Apache-2.0-Drittanbieterhinweisen, HACS-Metadaten und Health-Automatik-Roadmap bleiben unverändert Bestandteil der Vorbereitung. Keine automatische Health-Erkennung oder andere neue Funktion eingeführt.

## Neue Artefakte (ersetzen die bisherige lokale Vorbereitung)

- `ha-assist-router-1.2.1-publication.zip`: vollständiger geprüfter Repositoryinhalt direkt an der ZIP-Wurzel; Tests, CI, Originalgrafiken und lizenzierte Referenzen eingeschlossen. Kein .git, .venv, .storage, Tempverzeichnis oder altes ZIP enthalten. Dieses ZIP nicht vollständig nach HA entpacken.
- `assist-router-1.2.1-public-baseline.zip`: separates manuelles Installationspaket; nur custom_components/assist_router nach HA übernehmen. HACS verwendet später den getaggten Quellbaum.
- `dist/SHA256SUMS.txt`: Prüfsummen der neu gebauten ZIPs. CRC, genaue Inhalte und Publikationsgrenzen prüft tools/build_release.py; ein wiederholter Build muss bytegleich sein.

Die frühere unbereinigte lokale Vorbereitung ist nicht zur Veröffentlichung zu verwenden. Die neuen Artefakte wurden bei unveränderter Versionsnummer neu erzeugt, da bisher noch kein öffentlicher Release erfolgt ist.
