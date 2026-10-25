# CI-Korrektur nach dem ersten öffentlichen Lauf

Version 1.2.1 und Config-Entry-Schema 3.1 bleiben bestehen. Kein produktiver Python-Code und keine Providerkonfiguration werden geändert.

## Reproduzierbare Quellenverträge

Die drei Generatoren schreiben ihre JSON-Ausgaben explizit mit UTF-8 und LF, unabhängig vom Betriebssystem. Die drei gespeicherten Ergebnisse sind entsprechend normalisiert. Die unveränderten Upstream-Referenzen werden weiterhin als Originalbytes gespeichert; SHA-256-Nachweise und die strikte `git diff --exit-code`-Prüfung bleiben erhalten.

Für `prompt_contracts.json` ändert sich ausschliesslich die Dateikodierung der Zeilenenden, kein JSON-Wert. Der aktuelle SHA-256 steht in der Baseline. Der frühere CRLF-Hash bleibt zusätzlich erhalten: Der Repository-Check rekonstruiert die damaligen CRLF-Bytes und prüft deren ursprünglichen Hash. So kann die Normalisierung keine Inhaltsänderung verbergen. Alle übrigen produktiven Dateien behalten ihre bisherigen Byte-Hashes.

Regressionen führen alle drei Generatoren zweimal auf den gepinnten Referenzen aus und vergleichen die Ergebnisse bytegenau mit den eingecheckten Dateien. Sie verlangen explizite UTF-8-/LF-Ausgabe, unveränderte Referenzbytes und weisen manipulierte Vertragsinhalte auch bei geändertem aktuellem Baseline-Hash zurück.

## Echte HA-Laufzeit

Der isolierte Linux-Job installiert `requirements-test-ha.txt`. Neben dem HA-Paket enthält es die drei exakten Anforderungen aus dem Conversation-Manifest von HA 2026.10.2. Sie müssen bereits vor dem ersten Conversation-Import vorhanden sein. Der Import-Guard bleibt aktiv; fehlende Pakete können deshalb keinen grünen Collection-Skip erzeugen.

`tests_live` prüft die tatsächliche HA-Version und die Übereinstimmung mit dem installierten Conversation-Manifest. Die vorhandenen vier Kombinationen aus Promptmodus und erfolgreicher/unklarer Ausführung bleiben erhalten: echte Conversation-Entities, HA-ChatLog, Rückfragen, Unicode und kein zweiter Agent-Aufruf nach unklarem Ergebnis. Kein produktiver HA-Server und keine Providerinferenz werden angesprochen.

Lokal ohne Linux/HA sind die Quellenvertragstests ausführbar. Die verbindliche echte Laufzeitprüfung erfolgt im separaten GitHub-Job; ein lokaler Skip zählt nicht als Erfolg.
