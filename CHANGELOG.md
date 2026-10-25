# Änderungen

## Öffentliche Vorbereitung 1.2.1 – notwendige URL-Bereinigung

- Private Default-URL aus der historischen 1.0-Migration entfernt. Explizit gespeicherte Endpunkte bleiben unverändert; bei fehlender/ungültiger URL atomarer Abbruch ohne Config-Entry-Änderung.
- Schema 3.1, zentrale Prompts, Agentenreihenfolge, Freigaben, Health-Checks und Sicherheitslogik unverändert. Keine automatische Neufreigabe oder neue Versionsnummer.
- Kompatibilität und sicherer HACS-Übergang einschliesslich Legacy-Sonderfall dokumentiert; Publikationsscan verhindert neue private Endpoint-Literale.

## 1.2.1

- Pauschale Local-OpenAI-Sperre durch eine enge, wertabhängige Parameterfreigabe ersetzt: `reasoning_effort=none`, konstant deaktiviertes `enable_thinking` für den geprüften llama.cpp-Pfad.
- Key/Value-Schema und tatsächliche Extra-Body-Zusammensetzung geprüft. Konstante Literale und kleine konstante Jinja-Ausgaben werden ohne Rendering erkannt; unbekannte Parameter, dynamische Ausdrücke, doppelte/mehrdeutige Schlüssel und widersprechende native Thinking-Optionen bleiben gesperrt.
- Alle Rohparameter bleiben unverändert Bestandteil des vollständigen Konfigurations-Fingerprints. Auch eine erlaubte Änderung, Entfernung oder äquivalente Textform verlangt erneute Freigabe und eine neue Conversation.
- Keine Änderung bestehender Integrationen oder ihrer Konfiguration; ausgeschalteter Modus und Schema 3.1 unverändert. Bestehendes 1.1.0-Verhalten bei deaktivierter Zusatzverwaltung erhalten.
- Regressionstests für Parameterpolitik, Fingerprints und die echten Local-Request-Builder mit Jinja2 3.1.6 (Testabhängigkeit) ergänzt.

## 1.2.0

- Optionale gemeinsame mehrzeilige Geschäftsanweisungen und Ergänzungen pro Entity über HA-Dialoge.
- Standardmässig aus; Migration von Schema 1/2 auf 3.1 schreibt nur den Router-Eintrag und erhält das bisherige Verhalten.
- Geführte manuelle Neutralisierung bestehender Agent-Prompts; keine automatischen Änderungen fremder Integrationen.
- Lesende Registry-/Subentry-/Quellprüfung mit exakten Baselines und sichtbaren SHA-256-Fingerprints. Unbekannte oder geänderte aktive Ziele blockieren den Zusatzmodus vor Übergabe.
- Gepinnte Kompatibilitätsadapter für HA OpenAI/Google 2026.10.2 und geprüfte Local-OpenAI-Quellen; freie Local-Request-/Chat-Template-Parameter werden im Zusatzmodus konservativ abgewiesen.
- Stabile literale Zusammensetzung ohne Unicode-Normalisierung. Agent-Ergänzungen bleiben beim Sortieren an die Entity gebunden.
- Promptrevisionen und dauerhafte Stale-Markierung erzwingen neue Conversations nach Konfigurationsänderungen; bestehende Safety-Sperren bleiben erhalten.
- Keine Exklusivitäts-, Cache-Treffer- oder Exactly-once-Garantie. Kein Core-Patch, keine Zielintegrations-, Pipeline- oder Automationsänderung.
- Tests, Prüfbericht, Installations-/Quell-ZIP und reproduzierbare Quellenfreigabe ergänzt.

## 1.1.0

- Beliebig viele vorhandene Conversation-Entities mit freier Reihenfolge; keine festen Providerrollen im Routing.
- HA-Entity-Selektor mit `multiple`/`reorder`; Positionsdialog als Alternative.
- Aktivieren, Deaktivieren, Hinzufügen und Entfernen; mindestens ein aktiver Eintrag.
- Atomarer Konfigurationsentwurf mit explizitem Speichern.
- Optionale unabhängige Health-Prüfung je Entity: HTTP-Status und LM Studio.
- Endpunkt, Authentifizierung (keine/Bearer/Basic), erwarteter HTTP-Status, Modell-/Instanzstatus und Cache-Zeitbudgets pro Agent konfigurierbar.
- Health-Registry für spätere Prüftypen; keine Providerkenntnis im Routing.
- Automatische Migration von 1.0.0, unter Beibehaltung von Reihenfolge, Health-Zuordnung und Zugangsdaten.
- Sicherheits-Ledger, konservative Delegation, Kontext und Unicode-Verhalten beibehalten.
- Tests für Migration, HA-Selektoren, generische Listen und unabhängige Health-Prüfungen ergänzt.

## 1.0.0

- Erste konservative Delegation bestehender lokaler, OpenAI- und Gemini-Agents.
- LM-Studio-Modellprüfung, Kontextfortsetzung und Sperre bei unklaren Ausführungsergebnissen.
