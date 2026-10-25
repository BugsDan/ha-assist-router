# Zentrale Promptverwaltung: Kompatibilitätsprüfung für Zielversion 1.2.0

Stand: 23. Oktober 2026. Private Netzwerkadressen wurden für diese öffentliche Vorbereitung durch Beispielhosts ersetzt; die Originalquellen und Commit-Hashes bleiben unverändert. **Ergänzung 1.2.1:** Die pauschale Parametersperre aus 1.2.0 wurde durch eine enge Freigabe für konstantes `reasoning_effort=none` und `enable_thinking=false` im geprüften llama.cpp-Pfad ersetzt. Auch diese Parameter bleiben vollständig fingerprinted. Gültige Formen und Grenzen stehen in PROMPT_VERWALTUNG.md. Ergebnis: **Keine zuverlässige exklusive Ersetzung vorhandener Agent-Systemprompts über `extra_system_prompt`.** Assist Router 1.2.0 implementiert deshalb die nachfolgend begründete Alternative **„Zentrale Geschäftsanweisungen als Zusatz“**. Sie ist standardmässig ausgeschaltet. Bedienung, Fingerprints, Neutralisierung und Fehlermeldungen sind in [PROMPT_VERWALTUNG.md](PROMPT_VERWALTUNG.md) beschrieben.

## Tatsächlich geprüfte Implementierungen

| Ziel | Geprüfte Quelle | Ergebnis |
|---|---|---|
| OpenAI Conversation | HA-Core-Tag 2026.10.2, Handler und Request-Konverter | Reicht eigenen `CONF_PROMPT` **und** `user_input.extra_system_prompt` an HA weiter. Der resultierende HA-Systemtext wird für die Responses API in eine Developer-Nachricht konvertiert. |
| Google / Gemini Conversation | HA-Core-Tag 2026.10.2, Handler und Request-Aufbau | Reicht ebenfalls eigenen Prompt und Extra weiter. Normalerweise landet der gesamte Text in `system_instruction`. Für bestimmte Modelle verwendet die Integration stattdessen User-/Model-History; das ist keine universelle Garantie einer Systemrolle. |
| Local OpenAI LLM, Servertyp llama.cpp | skye-harris/hass_local_openai_llm, Tag 1.13.0, Commit `37b2334b2c5e5085a0c1081092fff238980e27ac` | Die llama.cpp-Entity erbt den gemeinsamen Conversation-Handler. Dieser übergibt eigenen Prompt und Extra an HA. Der Konverter erhält den zusammengesetzten Text als Systemnachricht. Der llama.cpp-Mixin ergänzt nur bei Assistant-Nachrichten gegebenenfalls Reasoning-Inhalte; er ersetzt den Systemprompt nicht. |

Der Nutzer hat Repository, Servertyp llama.cpp, LM-Studio-Backend `http://lmstudio.example:1234/v1` und Modell `google/gemma-4-12b-qat` bestätigt. **Die installierte Versionsnummer ist unbekannt.** Die geprüfte Repository-Fassung ist ein Versionsnachweis für diese Quelle, keine Aussage über den installierten Code. Zusätzlich nennt die Manifestdatei unter dem Release-Tag 1.13.0 intern Version 1.12.1. Deshalb werden Commit und SHA-256 festgehalten statt aus dem Release-Namen eine installierte Version abzuleiten.

Es wurden keine Modellanfragen, Werkzeugaktionen oder Änderungen an Zielintegrationen ausgeführt. Insbesondere sind tatsächliche Modellausgaben, die LM-Studio-Chatvorlage und die installierte Local-OpenAI-Fassung nicht live abgenommen. Der Source-Test belegt die Weitergabe und den Request-Aufbau, nicht die semantische Befolgung durch ein Modell.

## Warum eine ausschliessliche Ersetzung nicht funktioniert

HA `ChatLog.async_provide_llm_data` baut den Text in dieser Reihenfolge zusammen:

1. Agent-eigener Prompt, als HA-Template gerendert. Ein leerer Wert führt über `user_llm_prompt or llm.DEFAULT_INSTRUCTIONS_PROMPT` zum HA-Standardprompt.
2. Anweisungen der ausgewählten LLM-/Tool-API, sofern vorhanden.
3. Gegebenenfalls dynamische Datums-/Zeitanweisungen, sofern kein entsprechendes Zeitwerkzeug vorhanden ist.
4. `user_extra_system_prompt`, andernfalls der zuvor im ChatLog gespeicherte Extra-Prompt.

`extra_system_prompt` ist daher **eine Ergänzung**. Ein früherer Agent-Prompt mit beispielsweise abweichenden Einkaufslistenregeln bleibt Teil desselben effektiven Texts. Eine Anweisung „Ignoriere die vorherigen Regeln“ ist keine zuverlässige technische Konfliktlösung. Ebenso wenig sind leere Agent-Prompts ein zuverlässiger Ausschalter.

Vorheriges Setzen von `chat_log.content[0]` im Router hilft nicht: Der Ziel-Agent baut diesen Eintrag erneut auf. Seine privaten Methoden mit geänderten Parametern aufzurufen, sein Config Entry automatisch umzuschreiben oder seine Tool-API abzufangen wäre eine andere, integrationsspezifische Lösung mit zusätzlichen Risiken. Das gehört nicht in diesen Router und wurde nicht implementiert.

**Folge:** Ein gemeinsamer Text kann bei den geprüften Fassungen zusätzlich ankommen. Ein einziger exklusiver Router-Systemprompt unter Ausschluss alter Agent-Anweisungen ist damit nicht nachgewiesen und über diese Schnittstelle nicht durchsetzbar. Auch die Anweisungen bestehender Tool-Integrationen wie Yuvomi MCP wirken weiterhin mit und dürfen nicht stillschweigend entfernt werden.

## Ein weiterer konkreter Alt-Prompt-Fall

HA verwendet `user_extra_system_prompt or self.extra_system_prompt`. Nach einmaliger Übergabe eines gemeinsamen Prompts können `None` und ein leerer String im selben Chat dessen alten Text deshalb weiterverwenden. Ein Abschalten oder Ändern eines künftigen Router-Promptmodus darf nicht einfach nur das neue Extra-Feld leeren. 1.2.0 prüft deshalb Conversation-Revisionen.

Eine sichere Umsetzung muss Prompt-Revisionen pro Conversation verfolgen. Bei Änderung, Aktivierung oder Deaktivierung sind alte Conversations vor einer weiteren Agent-Übergabe anzuhalten und als neues Gespräch zu beginnen. Bestehende Historie wird nicht privat umgeschrieben; es erfolgt keine automatische Wiederholung einer Aktion. Das gilt auch für entfallene Agent-Ergänzungen und offene Rückfragen.

## Cachefreundlichkeit und ihre Grenzen

Der Router kann den statischen gemeinsamen Text und den statischen Agent-Zusatz pro Konfigurationsrevision einmal zusammensetzen. Keine Zeitstempel, zufälligen IDs oder laufenden Revisionsnummern in diesen Text einbetten. Anfragebezogenes `extra_system_prompt` separat am Ende erhalten, statt es zu überschreiben. Strings werden nicht normalisiert, damit Unicode und absichtliche Formatierung stabil bleiben.

Das verbessert lediglich die Stabilität des Zusatzteils. HA kann dynamische Zeit-/Tool-Anteile **vor** dem Extra-Prompt einfügen. Ein konstanter Zusatz ist deshalb nicht automatisch ein konstanter vollständiger Prompt-Präfix. Der Router kann diese Reihenfolge nicht über `extra_system_prompt` ändern. Ein vorhandenes GetDateTime-Werkzeug kann den von HA ergänzten Uhrtext entfallen lassen; dies darf der Router aber nicht durch ungefragtes Verändern der Werkzeuge erzwingen.

OpenAI verwendet im geprüften Request-Aufbau einen agentbezogenen `prompt_cache_key`; dies ist keine Cache-Garantie und erzeugt keinen gemeinsamen Cache über verschiedene Agent-Subentries oder Anbieter. Gemini-/LM-Studio-Caches und ihre Voraussetzungen bleiben Sache der jeweiligen Integration beziehungsweise des Servers. Tool-Reihenfolge, Modellvorlagen und gespeicherte Providerdaten liegen ebenfalls ausserhalb dieser Zusage.

Der Extra-Prompt wird vom HA-Assembler nicht nochmals als Jinja-Template gerendert. Ein Text wie `{{ now() }}` bleibt dort ein Literal. Ein eventuelles dynamisches Router-Template wäre eine gesonderte Funktion mit eigenem Rendering- und Fehlerkonzept, nicht ein stillschweigendes Merkmal der Extra-Schnittstelle.

## Empfohlene sichere Alternative in 1.2.0

Die Alternative heisst ausdrücklich **„Zentrale Geschäftsanweisungen als Zusatz“**, nicht „Agent-Systemprompts ersetzen“. Dafür ist kein Fork und keine Codeänderung an den Zielintegrationen nötig, wohl aber eine einmalige bewusste Prüfung ihrer Konfiguration in der vorhandenen HA-Oberfläche.

1. **Migration standardmässig ausgeschaltet.** Bestehendes Routing, Health-Checks und bisherige Weitergabe von `extra_system_prompt` bleiben nach dem Update identisch. Keine automatische Aktivierung oder Veränderung anderer Config Entries.
2. **Alte Geschäftsregeln einmalig aus den Ziel-Prompts entfernen.** In jedem Ziel-Agent einen kurzen, identischen und nicht leeren neutralen Basisprompt konfigurieren. Beispielsweise: „Verwende die für diese Anfrage bereitgestellten gemeinsamen Anweisungen sowie die von Home Assistant bereitgestellten Werkzeuge und Berechtigungen.“ Die Formulierung ist ein Baseline-Vorschlag, keine Ersetzungsfunktion. Tool-API-Anweisungen bleiben bestehen und sind mitzuprüfen.
3. **Readonly-Prüfung vor Aktivierung.** Für unterstützte, tatsächlich identifizierte Implementierungen den gespeicherten Basisprompt über Entity-Registry, Config Entry und Subentry eindeutig zuordnen. Unbekannte Versions-/Konfigurationspfade nicht raten. Nicht neutrale, unbekannte oder nicht überprüfbare aktive Ziele verhindern die Aktivierung des gemeinsamen Modus. Ohne Nachweis keine Kompatibilitätsbehauptung.
4. **Prüffingerabdruck statt nur Bestätigungskästchen.** Geprüfte Implementierung, Basisprompt und relevante Zusatzkonfiguration fingerprinten. Vor späteren Übergaben Änderungen erkennen und vor einem LLM-Aufruf mit verständlichem Hinweis stoppen. Keine automatische Änderung des Agents und kein stilles Ausweichen auf Cloud, nur weil eine Promptprüfung fehlschlägt. Ein Fingerabdruck beweist nicht die Konfliktfreiheit gerenderter Templates oder Tool-Anweisungen; diese Grenze bleibt sichtbar.
5. **Gemeinsamer Text und individuelle Ergänzungen im Router.** Globales mehrzeiliges Feld und optionales Feld je Entity. In fester Reihenfolge zusammensetzen: gemeinsamer statischer Text, statischer Agent-Zusatz, unveränderte anfragebezogene Extra-Anweisungen. Keine Modellnamen oder Providerrollen im generischen Routing.
6. **Neue Prompt-Revision, neues Gespräch.** Änderung oder Deaktivierung verlangt neue Conversations. Das Safety-Ledger für unklare Aktionen bleibt davon unabhängig erhalten; Konfigurationsänderungen dürfen solche Sperren nicht beseitigen.
7. **Abnahme an allen drei echten Ziel-Agents.** Harmloser, eindeutiger Testtext ohne Schreibwerkzeuge plus kontrollierte Einsicht in den jeweils finalen Modellrequest. Installierte Local-OpenAI-Version und llama.cpp-Mixin dabei mitprüfen. Promptinhalte nicht dauerhaft in Router-Diagnosen protokollieren.

Diese Alternative schafft einen zentral gepflegten Ort für die eigentlichen Geschäftsregeln, während notwendige neutrale und werkzeugbezogene Anteile technisch bei HA/den Agents bleiben. Ohne die einmalige Neutralisierung oder eine entsprechend sichtbare Koexistenzprüfung könnte der Router widersprüchliche Alt-Prompts weiterhin nicht ausschliessen.

## Implementierte Entscheidung

1.2.0 setzt die Alternative mit Prompt-UI, lesender Fingerprintprüfung und Revisionsgrenzen um. Die Baseline-Neutralisierung bleibt ein bewusst manueller Schritt in den Zielintegrationen. Ohne passende installierte Quellen und aktuelle Freigaben lässt sich der Zusatzmodus nicht aktivieren. 1.1.0-ZIPs bleiben als historische Pakete erhalten; das neue Paket aktiviert keine Promptmigration automatisch.

Die im Nutzer-HA installierte Local-OpenAI-Fassung und die finalen Modellrequests wurden nicht live geprüft. Die Quellenfreigabe schützt davor, aus der bekannten Repository-Fassung ungeprüft auf eine andere Installation zu schliessen.

## Nachweise und Reproduktion

- `tools/check_prompt_compatibility.py`: Quellen lesend laden und Verträge prüfen.
- `docs/prompt_compatibility_evidence.json`: URLs, Commit, SHA-256 und Versionsgrenzen.
- `tests/test_prompt_compatibility.py`: Zusatz und alter Basisprompt gleichzeitig, HA-Default bei leerem Basisprompt, Überschreiben vorbelegter Systemtexte, Tool-Anweisungen, Zeitanteile, Alt-Extra bei None/Leerstring, Literal-Templates, Unicode sowie OpenAI-/Google-/Local-Transportaufbau.
- `docs/prompt_compatibility_regression_results.xml` und `docs/prompt_compatibility_validation.json`: abschliessender Testlauf einschliesslich bestehender Router-Tests.

```sh
python tools/check_prompt_compatibility.py
python -m pytest tests/test_prompt_compatibility.py -q
python -m pytest tests tests_live -q --junitxml=docs/prompt_compatibility_regression_results.xml
```

Die Tests führen ausgewählte unveränderte Quellfunktionen mit Host-/SDK-Doubles aus. Sie rufen keine LLM-Dienste auf und belegen keine Modellbefolgung. Für den Gemini-Request-Aufbau wird mit null Inferenziteration nur die tatsächlich erzeugte Konfiguration erfasst.

Quellen: [HA ChatLog 2026.10.2](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/components/conversation/chat_log.py), [OpenAI-Handler](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/components/openai_conversation/conversation.py), [OpenAI-Request-Konverter](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/components/openai_conversation/entity.py), [Google-Handler](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/components/google_generative_ai_conversation/conversation.py), [Google-Request-Aufbau](https://github.com/home-assistant/core/blob/2026.10.2/homeassistant/components/google_generative_ai_conversation/entity.py), [Local-OpenAI-Handler, gepinnter Commit](https://github.com/skye-harris/hass_local_openai_llm/blob/37b2334b2c5e5085a0c1081092fff238980e27ac/custom_components/local_openai/conversation.py), [llama.cpp-Mixin](https://github.com/skye-harris/hass_local_openai_llm/blob/37b2334b2c5e5085a0c1081092fff238980e27ac/custom_components/local_openai/entities/llama_cpp.py), [Local-OpenAI-Request-Konverter](https://github.com/skye-harris/hass_local_openai_llm/blob/37b2334b2c5e5085a0c1081092fff238980e27ac/custom_components/local_openai/entity.py).

## Testergebnisse

Die historische Machbarkeitsprüfung ergab 115 bestandene Tests und eine übersprungene echte HA-Sammlung. Der aktuelle Implementierungs-/Regressionslauf steht in [PRUEFBERICHT.md](PRUEFBERICHT.md) und `test-results.xml`. Die Paketprüfung und SHA-256-Werte werden nach diesem Lauf erzeugt. Die Aussage über unveränderte 1.1.0-Dateien bezieht sich ausschliesslich auf die damalige Untersuchung, nicht auf den neuen 1.2.0-Code.
