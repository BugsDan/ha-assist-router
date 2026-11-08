# Assist Router 1.3.0: Standard und Strict

Lokale Entwicklung auf `development/1.3.0`. Kein Commit, Push, Tag, Release oder produktiver HA-Eingriff ist Teil dieser Abnahme. Veröffentlichte Baseline bleibt v1.2.1.

## Vertrauensmodell

Es gibt zwei Modi und den bestehenden Schalter für zentrale Prompt-Zusätze. Der Schalter bleibt unabhängig: ausgeschaltet gilt die unveränderte Weitergabe an beliebige bestehende Agents, ohne fremde Konfiguration oder Quellen zu inspizieren.

- **Standard:** einmalige ausdrückliche Freigabe der konkreten Agentenidentität und des Backend-Vertrauensbereichs. Kein exakter Quell-, Versions-, Modell- oder Gesamtkonfigurationshash. Laufzeitprüfung bekannter Konfigurationspfade vor dem Routing und erneut nach wartenden Health-Checks.
- **Strict:** unveränderte Quellverträge, Methodenzuordnung, HA-ChatLog-Prüfung und vollständiger Konfigurationsfingerprint aus 1.2.1. Änderungen an Modell, Parametern, Zugangsdaten oder Quellen verlangen weiterhin Review. Local OpenAI 1.14.0 bleibt hier absichtlich nicht freigegeben.

Standard verwendet denselben Inspector/Manager und dieselbe Promptweitergabe; es gibt keine neue Adapterhierarchie, Provider-Clients oder Tool-Wrapper. Er kennt die Config-Entry-/Conversation-Subentry-Strukturen von `local_openai`, `openai_conversation` und `google_generative_ai_conversation`. Ohne bekannten lesbaren Basispromptpfad ist die zentrale Verwaltung nicht freigabefähig. Ein Experimental-Modus wurde bewusst nicht ergänzt.

### Dauerhafte Standard-Freigabe

Gespeichert wird unter `prompt.approvals[entity_id]` ein SHA-256 über den **Vertrauensbereich**, kein Quellcode-Fingerprint. Er umfasst Entity-ID, Registry-Unique-ID, Integration, Config-Entry-/Subentry-ID sowie den bekannten Backend-/Authentifizierungsbereich. Die normale HA-Config-Entry-Persistenz speichert diesen Wert in den Router-Optionen. Er wird bei Neustart/Reload wieder gelesen; keine Zustimmung wird nur im RAM gehalten.

Zum Backend-Vertrauensbereich zählen explizite API-Ziele einschließlich Pfad, Servertyp, effektive zusätzliche Header, Retrieval-Host sowie bekannte API-Zugangsdaten und Organisations-/Projektangaben. Die Werte selbst werden weder in der Freigabe kopiert noch in Diagnosemeldungen ausgegeben. Authentifizierungs-/Tenant-Wechsel und geänderte Routing-Header können denselben Host anders verwenden und verlangen daher ebenfalls bewusste neue Bestätigung. Tokenrotation ist damit eine sicherheitsrelevante Änderung.

Modell-ID, gewöhnliche Sampling-/Thinking-Parameter, Integrationsversion, Chat-History-Limit und andere gewöhnliche Einstellungen gehören nicht zur Standard-Freigabe. Bekannte leere Default-Felder werden kanonisiert, damit ein Update allein durch explizite leere Defaults keine Freigabe invalidiert. Ein anderer Agent mit wiederverwendeter Entity-ID erbt keine Zustimmung.

Für Local OpenAI 1.14.0 ist `entry.data` massgeblich: Daraus liest die Integration API-Ziel, API-Key (mit dem Standardwert `local-openai` bei leerem Key), zusätzliche Header, Servertyp sowie Weaviate-Host und -API-Key. Widersprechende sicherheitsrelevante Werte in `entry.options` blockieren die Prüfung mit `conflicting_backend_config`; eine Freigabe kann diesen Konflikt nicht überstimmen. Bei aktivem Weaviate-Host zählt auch dessen API-Key zum Fingerprint. Frühere Freigaben aus diesem unveröffentlichten Entwicklungsstand müssen bei geändertem Fingerprint einmal neu bestätigt werden. Strict-Fingerprints bleiben unverändert.

Endpoint- oder Identitätsänderung meldet `agent_or_backend_changed`. Im Review-Dialog muss der aktuelle sichere Zustand erneut ausdrücklich bestätigt und anschließend gespeichert werden. Eine Änderung zwischen Anzeige und Bestätigung wird verworfen. Alte Freigaben werden niemals automatisch überschrieben.

## Konfigurationsprüfung und Fehler

| Kategorie | Beispiele | Verhalten |
| --- | --- | --- |
| Sicherheitsblockade | Basisprompt nicht neutral; zusätzlicher Systemprompt; Messages-/Tool-/Chat-Template-Override; dynamische Request-Templates; Vertrauensbereich geändert | Keine Übergabe; kein stiller Wechsel zu einem anderen Anbieter |
| Technischer Konfigurationsfehler | Fehlende Registry/Subentry; unbekanntes Konfigurationslayout; unlesbarer Backend-Bereich; fehlerhafte Parametersyntax | Zentrale Promptweitergabe blockiert, Ursache separat diagnostiziert |
| Nichtverfügbarkeit | Genehmigter Agent ist entladen oder ein Health-Check schlägt fehl | Vor Übergabe überspringen; bisheriger konservativer Fallback und Rückfragebindung bleiben wirksam |
| Nicht blockierende Warnung | Explizite Modellparameter, konkurrierende Thinking-Pfade, native Einstellungen überschreiben Request-Flags | Agentenfreigabe bleibt gültig; verständliche Anzeige und stabile Warncodes |
| Fehler nach Übergabe | Exception, Cancellation, fremde Conversation-ID, Agent-Fehlerresultat | Bestehende Sperre, kein Retry und kein Fallback |

Die Modellparameterprüfung ist nicht an konkrete Modelle gebunden und führt keine Templates aus. Bekannte Sampling-/Reasoning-Parameter sind in Standard unabhängig von der Freigabe. Unbekannte **Request-Body-Schlüssel** werden nicht pauschal als Modellparameter behandelt: Sie können Nachrichten oder Berechtigungs-/Tooldefinitionen überschreiben und bleiben als `unclassified_request_override` blockiert. Das verlangt eine gezielte Prüfung des Parameters, keine Übernahme eines neuen Modell-Fingerprints. Die Prüfung garantiert keine allgemeine Modell-/Backend-Kompatibilität.

Local OpenAI 1.14.0 wird in Standard über dieselben Konfigurationspfade unterstützt. Die neue `llamacpp_thinking_mode`-Verarbeitung kann `enable_thinking` überschreiben; das wird als Warnung behandelt. `reasoning_effort` ist im Standardmodus nicht auf `none` begrenzt. Tatsächliche Parameterverwendung und Wirkung bleiben bei Integration, Modell und Server.

Ein entladener Standard-Agent kann anhand seiner weiterhin lesbaren, neutralen Konfiguration und gespeicherten Identität geprüft bleiben. Es wird `agent_not_loaded` gewarnt; der Router delegiert ihm nicht. Ein fehlender oder abweichender Basisprompt wird dadurch niemals toleriert. Strict bleibt beim bisherigen Verhalten.

## Prompt- und Werkzeuggrenzen

Die zentrale Zusammensetzung bleibt literal und stabil: gemeinsamer Text, Agent-Ergänzung, eingehender anfragebezogener Zusatz. Übergabe weiterhin über `conversation.async_converse(..., extra_system_prompt=...)`. Keine Änderung existierender Systemnachrichten, keine Template-Auswertung, keine Provideranfrage durch den Router. Unicode und Werkzeugargumente werden nicht umgeschrieben.

Standard ist ausdrücklich Vertrauen in die Integration: Ein neutraler gespeicherter Prompt beweist nicht, dass Integration, HA, Retrieval, Werkzeuge oder Backend keine weiteren Anweisungen erzeugen. Der Router kann keine Prompt-Exklusivität, semantische Modellbefolgung, allgemeine SDK-/Backend-Retryfreiheit oder Exactly-once-Ausführung garantieren. Auch Strict garantiert diese Eigenschaften nicht.

HA-/MCP-Werkzeuge werden ausschließlich über die vorhandenen Agents und Werkzeuganbieter ausgeführt. Auswahl, Berechtigungen, Validierung und Yuvomi-Schreibschutz bleiben dort. Der Router erteilt keine zusätzlichen Rechte und installiert keinen MCP-Bypass. Diese Entwicklung ist keine erneute Prüfung der tatsächlichen produktiven Yuvomi-Konfiguration.

DNS-/Proxy-Änderungen, serverseitige Modell-/Templateänderungen oder neue intern erzeugte Anweisungen einer aktualisierten Integration sind nicht allein durch gespeicherte Konfigurationswerte erkennbar. Bei inkompatibel geändertem Konfigurationslayout kann auch Standard technisch blockieren; die gespeicherte Zustimmung wird dadurch nicht gelöscht.

## Migration, Gespräche und Health-Checks

Config-Entry-Schema ist 3.2. Vorhandene 1.2.1-/ältere Einträge migrieren atomar zu **Strict**, einschließlich ausgeschaltetem Promptmodus. Reihenfolge, Aktivierung, Health-Einstellungen, Prompttexte, Ergänzungen und bestehende Strict-Reviews bleiben erhalten. Keine fremden Config Entries werden geschrieben. Fehlgeschlagene Validierung hinterlässt den Ursprung unverändert.

Neue Einrichtungen starten mit Standard, aber zentralen Zusätzen weiterhin **ausgeschaltet** und ohne vorweggenommene Agentenfreigabe. Strict → Standard verlangt ein separates ausdrückliches Häkchen; Strict-Hashes sind keine Standard-Zustimmung. Vorhandene Standard-Zustimmungen bleiben bei einem Moduswechsel gespeichert, werden in Strict aber nicht verwendet.

Änderungen zentraler Prompts, aktiver Ergänzungen, Freigaben oder des aktiven Modus verlangen neue Gespräche. Die Strict-Gesprächsrevision bleibt für unveränderte alte Einstellungen kompatibel. Modell-/Parameterwechsel allein ändern die Standard-Revision nicht. Keine Konfigurationsänderung hebt eine bestehende Busy-/Blocked-/Stale-Sperre auf. Der Safety-Ledger bleibt bei Options-Reload erhalten, nicht bei HA-Neustart. Dauerhafte Zustimmung ist keine dauerhafte Aufzeichnung unklarer Aktionen.

Modellgebundene Health-Checks bleiben eine getrennte Konfiguration. Nach einem Modellwechsel können Modell-/Instanzschlüssel anzupassen sein; ihre Werte werden nicht als Agentenfreigabe verwendet und nicht automatisch aus unsicheren Annahmen überschrieben.

Ein Downgrade auf 1.2.1 benötigt das vorherige HA-Backup samt Config Entry. Nicht nur alte Dateien über Schema 3.2 kopieren.

## Datensparsame Diagnose

Diagnosen zeigen ausgewählten Agent, Sicherheitsmodus, Warncodes, Fehlerkategorie und das konfigurierte Modell, soweit lesbar. Das konfigurierte Modell beweist nicht, welche Instanz ein Auto-Modellresolver tatsächlich auswählt. Ohne lesbare Modellinformation wird kein Name geraten.

Für den letzten gestarteten Agent-Aufruf werden nur neue native ChatLog-Records gezählt: Toolaufrufe, Ergebnisse, explizite Fehler und Ergebnisse ohne auswertbares Fehlerflag. Keine Argumente, Werkzeugnamen, Rohresultate, Prompttexte, URLs, Zugangsdaten oder privaten Nachrichten. Es werden keine vollständigen ChatLogs serialisiert. Fehlende Sichtbarkeit heißt `not_observed`, nicht „garantiert keine Tools“. Provider mit privaten Logs oder extern ausgeführten Tools können nicht lückenlos beobachtet werden. Diagnoseauswertung kann keine Aktion verändern oder wiederholen.

HA- und Provider-eigene Logs bleiben außerhalb dieser Datensparsamkeitsgarantie. Der Router schreibt keine zusätzlichen Inhaltslogs.

Bei ausgeschalteten zentralen Zusätzen bleibt die fremde Konfigurationsinspektion aus; dann gibt es keine ausgelesene Modellangabe. Die Werkzeugzähler enthalten die zugehörige Agent-ID, damit parallele Gespräche nicht über die globale letzte Routingentscheidung falsch zugeordnet werden.
