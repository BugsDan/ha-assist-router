# Assist Router 1.2.1: Zentrale Geschäftsanweisungen als Zusatz

## Wirkung und sichere Einführung

Die neue Funktion ist bei Neuinstallation und Update **aus**. Ein Update schreibt nur den Router-Eintrag auf Schema 3.1. Es aktiviert keinen Promptmodus, neutralisiert keinen Agent und ändert weder Pipeline noch Einkaufslisten-Automation. Der bisherige Zusatzprompt wird ausgeschaltet unverändert durchgereicht, einschliesslich `None` und leerem String. Weiterhin „Befehle bevorzugt lokal verarbeiten“ in der Assist-Pipeline aktiviert lassen.

Einmalige Baseline-Migration bedeutet hier eine geführte **manuelle Konfigurationsänderung in den vorhandenen Agent-Dialogen**, keinen Schreibzugriff des Routers auf fremde Einträge. Dadurch kann jeder alte Prompt gesichert und bewusst übertragen werden. Der Router prüft das Ergebnis lesend. Er bietet keinen automatischen oder versteckten Migrationsschalter für Zielintegrationen an.

Empfohlener Ablauf im Wartungsfenster:

1. Bisherige Prompts sichern. Gemeinsame Geschäftsregeln im Router über **Konfigurieren → Gemeinsamen Prompt bearbeiten** eintragen, zunächst deaktiviert speichern. Je Agent sind über **Individuelle Agent-Ergänzung bearbeiten** weitere Anweisungen möglich; leer entfernt sie. Beide Textfelder sind mehrzeilig, bis 32768 Zeichen, wörtlich und ohne Jinja-Auswertung.
2. Für jeden aktiven Ziel-Agent in dessen eigenem HA-Dialog den Basisprompt durch folgenden **exakten**, nicht leeren Text ersetzen. Keine führenden/abschliessenden Leerzeichen oder zusätzliche Newlines ergänzen:

```text
Verwende die für diese Anfrage bereitgestellten gemeinsamen Anweisungen sowie die von Home Assistant bereitgestellten Werkzeuge und Berechtigungen.
```

3. Werkzeuge und deren Berechtigungen beibehalten; zusätzlich Tool-Prompts, exponierte Scripts, Retrieval-/Gedächtnisfunktionen und Backend-Vorlagen bewusst auf alte Geschäftsregeln prüfen. Agent-Reload abwarten. Die Baseline ist auch als kopierbares Nur-Lese-Feld im Router-Prüfdialog sichtbar. Zwischen Neutralisierung und Aktivierung fehlen die übertragenen Geschäftsregeln; währenddessen keine produktiven Assist-Aktionen auslösen.
4. Im Router **Agent-Basisprompt prüfen und freigeben** für jeden aktiven Agent öffnen. Nur `ready` kann freigegeben werden. Vollständige Konfigurations- und Quell-Fingerprints prüfen; das Bestätigungskästchen alleine umgeht keine Kompatibilitätsprüfung. Der Zustand wird beim Bestätigen erneut gelesen. Ändert er sich während eines offenen Formulars, muss der neue Fingerprint nochmals bewusst bestätigt werden.
5. Gemeinsame Zusätze aktivieren, additive Wirkung bestätigen und abschliessend **Speichern** wählen. Der gesamte Dialog ist ein Entwurf; Abbrechen verwirft Router-Änderungen. Er ändert keine bereits manuell gespeicherten Ziel-Agent-Einstellungen zurück.
6. **Neues Gespräch starten.** Dasselbe gilt nach gemeinsamer Promptänderung, Änderung einer Ergänzung eines aktiven Agents, Aktivierung/Deaktivierung des Modus sowie geänderten Review-Fingerprints. Neue aktive oder entfernte Agents verändern die Revision konservativ ebenfalls. Reine Reihenfolge-/Health-Änderungen tun das nicht.

## Was genau geprüft wird

Der Prüfer liest Entity-Registry, Config Entry und Conversation-Subentry. Der geladene Agent muss genau zu diesen Entry-/Subentry-Objekten passen. Er prüft den exakten Basisprompt, die gebundenen relevanten Methoden und SHA-256 ihrer vollständigen Quelldateien gegen eine installierte Quellenfreigabe. Auch HAs ChatLog-Assembler muss zum geprüften Quellstand passen. Es werden keine Templates ausgeführt, keine LLM-Requests oder Werkzeuge aufgerufen und keine Zielkonfigurationen geschrieben.

Nachgewiesene Quellen:

- HA OpenAI Conversation und Google Generative AI Conversation aus **2026.10.2**.
- Local OpenAI von skye-harris, Commit **37b2334b2c5e5085a0c1081092fff238980e27ac**, Tag 1.13.0 mit Manifest intern 1.12.1; geprüft sind gemeinsamer Handler/Request-Konverter und llama.cpp-Mixin. Das identifiziert nicht automatisch die installierte Version des Nutzers.

Die Freigabe hängt an Quellbytes und Methodenzuordnung, nicht allein am Versionsnamen. Abweichende Dateien, andere Implementierungen und unbekannte Konfigurationspfade blockieren. Es gibt keinen „trotzdem erlauben“-Schalter. Für Updates müssen die neuen Quellen nachvollziehbar geprüft, die Tests angepasst und die Router-Quellenfreigabe bewusst aktualisiert werden. Das generische Routing bleibt unabhängig von diesen speziellen Promptadaptern.

Ab 1.2.1 gilt eine enge Local-OpenAI-Parameterfreigabe statt der pauschalen Sperre aus 1.2.0:

| Speicherpfad / Schlüssel | Freigegebener Wert | Grenze |
|---|---|---|
| `request_body_opts.request_body_parameters`: `reasoning_effort` | `none` oder konstanter Jinja-Ausdruck `{{ 'none' }}` | Exakt der String `none`; kein `low`, `high`, Null oder dynamischer Ausdruck. |
| `chat_template_opts.chat_template_kwargs`: `enable_thinking` | `false`, `False` oder konstantes `{{ false }}` | Nur geprüfter llama.cpp-Mixin, dessen native `llamacpp_enable_thinking`-Option boolesch `false` ist oder fehlt (Default false). |
| Request-Body-Schlüssel `chat_template_kwargs` | Kleines konstantes Dictionary ausschliesslich mit `enable_thinking=false` | Beispielsweise `{'enable_thinking': False}` oder `{{ {'enable_thinking': false} }}`. Nur derselbe geprüfte llama.cpp-Pfad und kein HA-Legacy-Template-Modus. Der aktuelle Local-OpenAI-Dialog bevorzugt den separaten Chat-Template-Bereich und weist diesen Body-Schlüssel selbst als bereits konfigurierbar ab; der Router schreibt ihn nicht um. |

Die Werte sind die in Local OpenAI gespeicherten **Textwerte** der `Key`/`Value`-Zeilen, nicht neue Router-Einstellungen. Der Router rendert sie nicht und ändert sie nicht. Ein HA-Template-Feld kann einen konstanten Ausdruck enthalten; nur die kleine nachgewiesene Literal-Teilmenge wird erkannt. Sensorzugriffe, Funktionen, Filter, Bedingungen, weitere Template-Blöcke und andere Ausdrücke bleiben gesperrt. Weitere Modellparameter sind ohne gesonderten Nachweis ebenfalls gesperrt. Es gibt keinen allgemeinen Freigabeschalter.

**Wichtig zur tatsächlichen Implementierung:** Der geprüfte llama.cpp-Mixin setzt `chat_template_kwargs.enable_thinking` nach der Basiskonvertierung nochmals aus seiner nativen booleschen Option. Eine dort aktivierte oder als String gespeicherte Option darf einen ausdrücklich konfigurierten False-Wert nicht unbemerkt überschreiben und wird in dieser Kombination abgewiesen. Ein statisches `false` wird von HA zunächst als String behandelt; im geprüften Mixin wird es sicher durch boolesch False ersetzt. Für andere Serveradapter wird diese Eigenschaft nicht angenommen. `reasoning_effort=none` bleibt ein separater Body-Parameter. Ob das konkrete Backend damit Thinking wirklich deaktiviert, kann nur der Backend-Request-/Modelltest bestätigen.

Ein statischer JSON-Text `{"enable_thinking": false}` als einzelner **Value-String** ist nicht dasselbe wie ein tatsächlich gerendertes Dictionary: HAs statischer Parser verwendet Python-Literale, deshalb bleibt dieser Text ein String. Die Basiskonvertierung/Mixin-Verarbeitung erwartet hier ein Dictionary. Diese Form bleibt gesperrt; der Router repariert oder konvertiert sie nicht stillschweigend. Bereits vorhandene, gültige Key/Value-Konfigurationen mit den oben genannten Formen müssen nicht geändert werden.

Unbekannte oder promptverändernde Schlüssel wie `messages`, `prompt`, `system`, `system_prompt`, `chat_template`, `tools`, zusätzliche Template-Kwargs und unbekannte verschachtelte Felder bleiben gesperrt. Ebenso doppelte Schlüssel, nicht kanonische Schlüssel mit Rand-Leerzeichen, fehlerhafte Strukturen sowie gleichzeitiges Setzen von `enable_thinking` über beide Pfade. Leere UI-Zeilen werden wie von Local OpenAI ignoriert, bleiben aber im Fingerprint. Sonstige native llama.cpp-Einstellungen bleiben bestehen; sie werden nicht vom Router verändert.

**Erlaubt bedeutet nicht ungeprüft:** Alle Rohwerte, Schreibweisen, Reihenfolgen und verschachtelten Optionen bleiben unverändert im vollständigen Konfigurations-Fingerprint. Änderung, Hinzufügen oder Entfernen invalidiert die bisherige Freigabe – selbst wenn der neue Wert weiterhin erlaubt ist oder dieselbe Bedeutung hat (`false` gegenüber `{{ false }}`). Nach erneuter Freigabe ändert sich die Promptrevision; eine neue Conversation ist erforderlich. Ein nicht erlaubter Wert wird auch mit passendem manuell hinterlegtem Fingerprint abgewiesen.

Ein Export der konkreten produktiven Config Entries liegt hier nicht vor. Geprüft sind die vom Nutzer genannten Werte, das tatsächliche Schema und die Request-Builder des gepinnten Repositorys. Die Runtime-Prüfung liest die installierte Konfiguration unverändert aus; ein Live-Abnahmetest an diesem HA/LM Studio bleibt erforderlich. Ohne Zusatzmodus gilt die Parameterpolitik nicht, damit das 1.1.0-Verhalten unverändert bleibt.

Der Konfigurations-Fingerprint ist SHA-256 über kanonisches JSON aus Entity-/Entry-/Subentry-ID, Domain, geprüften Quellhashes, vollständigen Entry-Daten/Optionen und Subentry-Daten. Schlüssel werden sortiert; Strings bleiben exakt unverändert. Damit invalidieren auch Modell-, Werkzeug-, Server- oder Zugangsdatenänderungen eine Freigabe. Das ist bewusst strenger als ein reiner Promptvergleich. Geheimnisse gehen nur in die Berechnung ein; gespeichert/angezeigt wird der Hash, kein Rohwert. Hashes sind Vergleichsnachweise, keine Verschlüsselung und kein Schutz vor privilegierten Änderungen an HA oder am Router-Code.

Die Quelldateiprüfung erfolgt im HA-Executor und wird für die geladenen Methoden gecacht, bei Reload erneut. Die Konfigurationsprüfung erfolgt vor jeder Übergabe und erneut nach wartenden Health-Checks; kein zusätzlicher HTTP-Aufruf. Alle aktiven Agents müssen bestehen, auch wenn ein höher priorisierter Agent verfügbar wäre. Deaktivierte Ziele werden nicht geprüft. Im Zusatzmodus kann daher ein entladener, unprüfbarer Agent den gesamten Router-Promptmodus blockieren: nicht stillschweigend zur Cloud wechseln. Nach erfolgreicher Prüfung entscheiden die bisherigen Entity-/Health-Prüfungen unverändert über die Priorität.

## Zusammensetzung, Kontext und Cache

Feste Reihenfolge des übertragenen Extras: gemeinsamer Text, optionaler Agent-Zusatz, anfragebezogenes Extra des ursprünglichen Aufrufers. Zwischen vorhandenen Teilen stehen zwei Newlines. Fehlende optionale Teile entfallen. Kein Trim, Unicode-Normalisieren, Übersetzen oder JSON-Neuaufbau von Werkzeugargumenten. Statische Teile werden beim Options-Reload vorberechnet. Zeitstempel, Zufallswerte und Revisionsnummern werden nicht eingefügt. `{{ now() }}` bleibt ein Literal.

HA setzt davor weiterhin neutralen Agent-Prompt, gegebenenfalls Tool-API-Anweisungen und dynamischen Zeitkontext. Dadurch kann der komplette Promptpräfix trotz stabilem Zusatz wechseln. Providerbezogene Cache-Schlüssel und Chatvorlagen bleiben bei den vorhandenen Integrationen. Kein Cache-Treffer oder gemeinsamer Cache zwischen Providern wird zugesichert.

HA verwendet bei fehlendem/leerem Extra gegebenenfalls das frühere Extra im ChatLog. Daher löscht der Router alte Prompts nicht durch eine leere Übergabe. Stattdessen bindet er die Conversation an eine Revision. Ein Wechsel stoppt vor einer weiteren Übergabe und verlangt ein neues Gespräch. Eine abgewiesene Conversation bleibt auch nach Zurückstellen der Konfiguration veraltet. Vorhandene Historie bei verlorenem Ledger wird im aktiven Modus ebenfalls abgewiesen. Die Historie wird nicht privat umgeschrieben.

Offene Rückfragen bleiben beim bisherigen Agent. Promptänderungen gehen dieser Fortsetzung vor. Safety-Sperren wegen möglicherweise ausgeführter Aktionen bleiben unabhängig von Revisionen über Options-Reloads bestehen. Eine neue Conversation hebt diese Unsicherheit nicht sachlich auf: zuerst tatsächlichen Listen-/Gerätezustand prüfen. Ein bereits laufender Zielaufruf kann durch eine spätere Konfigurationsänderung nicht rückwirkend gestoppt werden.

## Grenzen der Exklusivität und Abnahme

Dies ist **keine exklusive Systemprompt-Ersetzung**. Werkzeug-/MCP-Prompts, dynamischer HA-Kontext, abgerufene Inhalte, Providerregeln, serverseitige Vorlagen, gespeicherte Providerdaten und anfragebezogene externe Extras können weitere Anweisungen enthalten. Ihr dynamischer Inhalt ist nicht Bestandteil der gespeicherten Agent-Konfiguration und kann sich ohne Fingerprintänderung verändern. Die manuelle Prüfung dieser Quellen bleibt erforderlich. Der Router garantiert weder semantische Modellbefolgung noch Konfliktfreiheit beliebiger externer Instruktionen.

Der Quellenvertrag beweist für die geprüften Python-Pfade die Übergabe an die bestehenden Request-Konverter. Die konkrete installierte Local-OpenAI-Fassung und die LM-Studio-Chatvorlage wurden nicht live abgenommen. OpenAI transportiert den zusammengesetzten Text als Developer-Nachricht; Google nutzt normalerweise `system_instruction`, bei bestimmten Modellen jedoch History. Das bleibt Sache der Zielintegration.

Vor Produktivbetrieb mit einer frischen Conversation und ohne Schreibwerkzeuge je Agent einen eindeutigen harmlosen Zusatz testen und dessen finalen Request kontrolliert im eigenen System prüfen. Keine Promptinhalte oder Zugangsdaten dauerhaft veröffentlichen. Danach Werkzeuge mit isolierten Testdaten prüfen; die hier nicht vorliegende Einkaufslisten-Automation auf Umgehung/Rückwege separat abnehmen. Keine Änderungen an Core, Local OpenAI oder Yuvomi MCP sind für die Router-Installation nötig.

## Statuscodes und Wiederherstellung

| Status | Bedeutung / nächster Schritt |
|---|---|
| `ready` | Quelle, Zuordnung und exakte Baseline passen; Review bewusst bestätigen. |
| `base_not_neutral` | Basisprompt im Ziel-Agent exakt migrieren, Reload abwarten. |
| `unknown_config` | Entity-/Subentry-Zuordnung fehlt oder ist nicht eindeutig unterstützt. |
| `unsupported_integration` | Kein geprüfter Promptadapter für diese Integration. Modus aus lassen oder Ziel deaktivieren. |
| `unknown_source` / `unknown_ha_source` | Installierter Quellstand ist nicht freigegeben. Kein Hash-Override; neue Version erst auditieren. |
| `agent_not_loaded` / `reload_required` | Agent nicht geladen oder Konfiguration noch nicht als passende Entity geladen. Reload abwarten. |
| `unsafe_request_overrides` | Unbekannter Schlüssel, nicht erlaubter/dynamischer Wert, widersprechende native Thinking-Option, mehrdeutige oder ungültige Struktur. Die enge Parameterfreigabe prüfen. |
| `opaque_config` | Konfiguration nicht verlustfrei kanonisch darstellbar. Keine willkürliche String-Konvertierung. |
| `review_changed_or_missing` | Konfiguration nicht freigegeben oder seit Freigabe verändert. Erneut prüfen, speichern, neues Gespräch. |
| `inspection_error` | Lesende Prüfung fehlgeschlagen; keine Übergabe. HA-/Routerzustand prüfen. |

Die Diagnostik zeigt Status, Revision, geprüfte und aktuelle Fingerprints pro zuletzt geprüftem Agent sowie Sitzungszähler; keine Prompttexte oder Secrets. Bei abgelehnter Prüfung stoppt die Auswahl sofort, daher sind nicht alle Diagnoseeinträge zwangsläufig vom letzten Turn. Die UI prüft jeden gewählten Agent frisch.

Abschalten des Zusatzmodus stellt für neue Gespräche die bisherige unveränderte Extra-Weitergabe her. Es setzt manuell neutralisierte Basisprompts nicht zurück; nötigenfalls deren gesicherte alten Werte bewusst im Ziel-Agent wiederherstellen. Ein Downgrade auf 1.1.0 erfordert das vorherige HA-Backup des Config Entry, da Schema 3 dort unbekannt ist.
