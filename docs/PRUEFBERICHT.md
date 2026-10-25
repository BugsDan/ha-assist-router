# Historischer Prüfbericht Assist Router 1.2.1 (vor Publikationsbereinigung)

Dieser Bericht dokumentiert den Stand vor der URL-Bereinigung. Aktuelle Migrationstests, Publikationschecks und Ergebnisse stehen in PUBLISHING_REVIEW.md und publication-validation.json.

Ziel: Home Assistant 2026.10.2. Umgebung: Windows / CPython 3.12.10. Ergebnis: **219 bestanden, 1 übersprungene echte HA-Sammlung, keine Fehler oder Fehlschläge**. JUnit-Dauer: 29.539 Sekunden. Details: `test-results.xml`, Befehle/Grenzen: `validation.json`. Gegenüber 1.2.0 sind 63 Parameter-Regressionsfälle hinzugekommen; bestehende Sicherheits-/Routingtests bleiben erhalten.

## Korrektur gegenüber 1.2.0

Die pauschale Sperre nicht leerer Local-OpenAI-Zusatzparameter wurde durch eine enge, wertabhängige Freigabe ersetzt. Keine Änderung am generischen Routing, Health-Transport, Safety-Ledger, Schema 3.1 oder ausgeschalteten Passthrough-Modus.

| Prüfung | Nachweis |
|---|---|
| Tatsächliches Local-Schema | Gepinnte `config_flow.py` und `const.py`: separate Key/Value-Listen für Request-Body und Chat-Template-Kwargs, Values als Templates. Quellen und Hashes in `prompt_compatibility_evidence.json`. Kein Export der produktiven Config Entries vorhanden. |
| Erlaubte Werte | `reasoning_effort=none` als exakter String bzw. kleiner konstanter Jinja-Ausdruck; `enable_thinking=false` über die dedizierten Kwargs und einen konstanten, richtig typisierten Dictionary-Wert im Body. Keine Änderung gespeicherter Werte. |
| Native Thinking-Option | Der tatsächliche llama.cpp-Mixin überschreibt `enable_thinking`. Explizites False wird nur bei nativer boolescher False-/Default-Einstellung und geprüftem Mixin freigegeben. True/String-Optionen bleiben gesperrt. Andere Serveradapter erhalten diese Annahme nicht. |
| Blockierte Schlüssel | Unter anderem `messages`, `system`, `prompt`, `chat_template`, `tools`, unbekannte oder zusätzliche verschachtelte Felder. Doppelte, mehrdeutige oder nicht kanonische Schlüssel und ungültige Strukturen ebenfalls gesperrt. |
| Blockierte Werte | Thinking True, unbekannter Reasoning-Wert, Null, Sensorzugriffe, Filter, Bedingungen, Template-Blöcke und Python-spezifische Stringformen ausserhalb der belegten Jinja-Teilmenge. Keine Template-Ausführung im Prüfer. |
| HA-Typgrenzen | Lowercase `false` als statischer Text bleibt zunächst String; geprüfter Mixin ersetzt ihn durch boolesches False. Statischer JSON-Dictionary-Text mit lowercase false wird nicht als Dictionary behandelt und bleibt gesperrt. Legacy-Template-Modus mit Body-Dictionaries wird abgewiesen. |
| Fingerprints erlaubter Parameter | Raw-Konfiguration unverändert gehasht. Erlaubte Wertänderung, äquivalente Schreibweise und Entfernen verändern den Fingerprint. Alte Freigabe wird abgewiesen; nach neuer Freigabe ändert sich die Conversation-Revision. |
| Fingerprints unsicherer Änderungen | `none` nach `high`, False nach True und native Thinking-Aktivierung verändern den Hash und werden als unsicher abgewiesen. Auch ein manuell passender Review-Hash umgeht die Parameterpolitik nicht. |
| Echte Request-Builder | Unveränderte `_get_extra_body_args` von Basis und llama.cpp-Mixin sowie `_async_handle_chat_log` ausgeführt. Final erfasste Requestargumente enthalten boolesches `enable_thinking=False`, erforderliches `reasoning_effort="none"` und unveränderten gemeinsamen Systemtext mit Unicode. Kein SDK-/Modellaufruf. |

## Testmethodik und beibehaltene Funktionen

Die Parameter-Transporttests verwenden die echten gepinnten Local-OpenAI-Quellfunktionen und Jinja2 **3.1.6**, dieselbe Version wie im HA-Tag. HAs statischer Ergebnisparser wird in diesen Host-Tests simuliert; seine Originalquelle wurde zusätzlich gelesen und gehasht. Damit wird kein vollständiger HA-Template-Lauf behauptet. Der produktive Prüfer nutzt nur AST-/Token-Erkennung einer kleinen konstanten Teilmenge und rendert keine fremden Templates.

Die gesamten bisherigen Regressionen bestehen: Default-off ohne Promptinspektion, Migration aus 1.0/1.1 nur im Router-Eintrag, mehrzeilige Prompt-UI und exakte HA-Selektorschemas, Readonly-Registry-/Subentry-/Quellprüfung, alle aktiven Ziele vor Übergabe geprüft, Recheck nach Health-/Executor-Awaits, unveränderte Prioritäten/Health-Caches, native HA-Intent-Vorverarbeitung und Satztrigger, Rückfragebindung, Conversation-ID und ChatLog.

Nach Übergabe weiterhin kein Retry/Fallback bei Fehlerresultaten, Exception, Timeout, Cancellation oder fremder Conversation-ID. Busy-/Blocked-Sperren, Schleifenschutz, Options-Reload, Unload und Session-Limit bleiben erhalten. Unicode, Systemtext und strukturierte Werkzeugargumente werden durch den Router nicht normalisiert oder umgeschrieben. Eine Konfigurationsänderung entsperrt keine möglicherweise ausgeführte Aktion.

Im ausgeschalteten Zusatzmodus werden fremde Parameter nicht inspiziert oder gefiltert: Das bisherige Verhalten aus 1.1.0 bleibt erhalten. Der Patch aktiviert nichts und schreibt weder Agent-Konfiguration noch Pipeline, HA-Core oder Einkaufslisten-Automation um.

## Grenzen / nicht ausgeführt

Die echte HA-Laufzeitsammlung wurde lokal mit einem Collection-Skip übersprungen: Hier fehlt Linux/Home Assistant 2026.10.2 mit Python >=3.14.2. `tests_live/` und CI sind vorbereitet, aber nicht remote ausgeführt. Kein sichtbarer HA-Frontend-Test, keine produktive Modellinferenz und keine Yuvomi-/Geräteaktion.

Die konkrete installierte Local-OpenAI-Version, produktive Config Entries und LM-Studio-Chatvorlage wurden nicht live gelesen oder verändert. Geprüft sind der mitgeteilte Parameterbedarf und die tatsächlichen gepinnten Schema-/Request-Pfade. Die installierte Konfiguration muss weiterhin die Readonly-Quellen-/Baseline-/Fingerprint-Prüfung bestehen. Ob Thinking im konkreten Gemma-Backend tatsächlich deaktiviert wird, erfordert abschliessende Request-/Backend-Abnahme; der Router verändert weder Modell noch Vorlage.

Promptverwaltung bleibt additiv. Keine Exklusivitäts-, semantische Modellbefolgungs-, providerübergreifende History-, Cache-Treffer- oder Exactly-once-Garantie. Fremde SDK-Retries, Tool-/MCP-Prompts, Retrieval und Backend-/Providerregeln bleiben ausserhalb der Routerkontrolle.

## Installation und Pakete

Schema 3.1 bleibt bestehen. Update von 1.2.0 erhält Modus und bestehende passende Reviews; Parameteränderungen verlangen erneute Freigabe. Migration von 1.1.0 lässt den Zusatzmodus standardmässig aus. Anleitung und gültige Key/Value-Formen: README.md und PROMPT_VERWALTUNG.md.

Der Release-Builder prüft CRC, genaue Inhalte, UTF-8-JSON, Pfade und Ausschlüsse. Installations-ZIP enthält eigenen Router-Code und Dokumentation, keine Core-/Providerreferenzen, Testabhängigkeiten, virtuelle Umgebung, temporären Pakete, Caches oder Bytecode. Das separate Quellen-ZIP enthält Tests und Referenzen. SHA-256 unter `dist/SHA256SUMS.txt`. Historische Installations-ZIPs 1.1.0 und 1.2.0 sind nachweislich unverändert.
