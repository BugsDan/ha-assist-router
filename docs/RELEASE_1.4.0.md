# Assist Router 1.4.0

Der Assist Router wählt den ersten verfügbaren Agenten gemäss der konfigurierten Priorität.

- Eine sortierbare Liste für aktive Agents; entfernte Agents behalten ihre Health-Einstellungen.
- Individuelle Health-Checks inklusive LM Studio und geladener Modelle bleiben erhalten.
- Der gemeinsame Prompt ergänzt den Prompt des jeweiligen Agents, sofern dieser Zusätze unterstützt.
- Die bisherigen Standard-/Strict-Freigaben und Quell-, Backend- und Parameterprüfungen entfallen. Agents und ihre Backend-Konfiguration liegen in der Verantwortung der Betreibenden.
- Bestehende Reihenfolge, Aktivierungen, Health-Checks und Prompts bleiben erhalten. Bisherige individuelle Router-Promptzusätze bleiben erhalten und können gesammelt entfernt werden.
- Keine automatische Wiederholung nach einem Agent-Aufruf; Rückfragen bleiben beim ursprünglichen Agenten.

**Update:** Vorher ein vollständiges HA-Backup erstellen. Den vorhandenen Config Entry beibehalten und nach dem Neustart ein neues Gespräch beginnen. Sicherheits- und Promptprüfungen werden nach dem Update nicht mehr durchgesetzt. Lokale HA-Intent-Verarbeitung weiterhin in der Assist-Pipeline aktivieren.

Health-Checks überprüfen keine Body-Parameter und garantieren keine spätere erfolgreiche Modellantwort. Beim Fallback an Cloud-Anbieter werden Anfragen an diese weitergegeben.
