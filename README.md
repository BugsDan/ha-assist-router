# Assist Router 1.4.0 für Home Assistant

Eigenständige Custom Integration für bestehende Home-Assistant-Conversation-Agents.

Der Router prüft die aktiven Conversation-Agents in der konfigurierten Reihenfolge und übergibt die Anfrage einmal an den ersten verfügbaren Agenten. Er verändert weder Agents noch HA-Pipelines oder Werkzeugberechtigungen.

**Wichtige Änderung gegenüber 1.3.0:** Die Standard-/Strict-Freigaben und Prompt-, Quellcode-, Backend- und Parameterprüfungen werden nicht mehr beim Routing durchgesetzt. Agenten und ihre Provider sind selbst vertrauenswürdig zu konfigurieren. Modell- und Credential-Wechsel erfordern keine Router-Freigabe mehr. Vor einem Update prüfen, ob diese Vertrauensänderung erwünscht ist.

## Installation und Update

In HACS `BugsDan/ha-assist-router` als benutzerdefiniertes Repository vom Typ Integration hinzufügen und Assist Router installieren. Home Assistant neu starten und die Integration unter **Einstellungen → Geräte & Dienste** hinzufügen. Bei einem Update den bestehenden Eintrag behalten, damit seine Einstellungen erhalten bleiben. Alternativ den Inhalt von `custom_components/assist_router` aus dem Release nach `/config/custom_components/assist_router` kopieren und HA neu starten. Vor jedem Update ein Backup anlegen.

## Bedienung

Unter Konfigurieren Agents auswählen und sortieren. Nicht ausgewählte Agents sind inaktiv, ihre Health-Einstellungen bleiben für eine spätere Auswahl erhalten. Pro aktivem Agent kann optional ein HTTP- oder LM-Studio-Health-Check konfiguriert werden. Ohne Health-Check entscheidet die HA-Entity-Verfügbarkeit. Einstellungen sind auch bei ausgeschaltetem Modell speicherbar. Abbrechen verwirft den ungespeicherten Entwurf.

LM Studio: `/api/v1/models`, exakten Modellschlüssel und Status **Geladen** konfigurieren. Nur vorhandene, aber nicht geladene Modelle sind mit der Einstellung **Vorhanden** ausdrücklich erlaubt. Health-Checks sind kurze, gecachte Vorabindikatoren; sie prüfen weder Request-Body noch tatsächliche Inferenzfähigkeit.

Ein optionaler gemeinsamer Prompt wird als Zusatz zum Prompt des Agents übergeben, sofern die Agent-Integration dies unterstützt. Er ersetzt den Agent-Prompt nicht; widersprüchliche Anweisungen sind möglich. Neue Einrichtungen bieten den einfachen englischen Assistentenprompt als deaktivierte Vorlage. Bestehende gemeinsame Prompts und bisherige individuelle Router-Zusätze werden unverändert übernommen; letztere können im Promptdialog gesammelt entfernt werden. Bei Promptänderungen ein neues Gespräch beginnen.

Bei nicht verfügbarem Agent erfolgt der Wechsel vor der Übergabe. Nach Übergabe erfolgt bei Fehlern oder unklarem Ergebnis **keine automatische Wiederholung**, weil Werkzeuge bereits Aktionen ausgeführt haben könnten. Eine offene Rückfrage bleibt an den ursprünglichen Agent gebunden. Mit Cloud-Fallback erhält der konfigurierte Anbieter die weitergereichte Anfrage. Lokale HA-Intent-Verarbeitung in der Assist-Pipeline aktiviert lassen.

Configs aus 1.3.0 bleiben samt Reihenfolge, Status, Health-Checks und Prompts erhalten. Für den späteren Wechsel: HA-Backup erstellen, bestehenden Config Entry behalten und keine Agenten oder Automationen löschen. Nach Neustart müssen unklare Aktionen geprüft und neue Gespräche begonnen werden; Laufzeit-Sperren leben nur im Speicher. Keine Datei in `.storage` manuell bearbeiten.

Lizenz: [MIT](LICENSE), Drittanbieter: [Hinweise](THIRD_PARTY_NOTICES.md). Historische Dokumente im Ordner `docs/` beschreiben ältere Versionen.
