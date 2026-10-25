# Assist Router 1.2.1: generische Konfiguration und optionale Prompt-Zusätze

## Zuständigkeiten

- `settings.py`: unveränderliche, streng validierte Agent-Liste und Health-Einstellungen; mindestens ein aktiver Agent, eindeutige Entity-IDs.
- `prompts.py`: optionale literale Zusätze, Registry-/Subentry-Prüfung, Quellenfreigabe, Konfigurations-Fingerprints und revisionsabhängige Conversation-Grenzen. Nur dieser Adapter kennt konkrete Prompt-Implementierungen.
- `prompt_contracts.json`: gepinnte Quellhashes, aus nachvollziehbarer Evidenz generiert; kein fremder Provider-Code im installierten Paket.
- `config_flow.py`: Entwurf, Entity-Auswahl, Sortierung/Position, Aktivierung und Health-Formulare. Persistenz erst beim expliziten Speichern. Die Health-Einstellungen sind Teil des Agent-Objekts und werden nicht über Listenindizes referenziert.
- `health_types.py`: Registry aus Prüftyp, Konfigurationsvalidator und Ergebnis-Predicate. Enthält nur die Health-spezifische LM-Studio-Kenntnis.
- `health.py`: gemeinsamer lesender HTTP-Transport, Zeit-/Grössenlimit, unabhängiger Cache pro Entity und Zusammenführung gleichzeitiger Prüfungen. `HealthChecks` benötigt keine Providerrolle.
- `runtime.py`: geordnete Auswahl aktiver Agents und Bindung offener Rückfragen. Keine Modellnamen, URLs, drei festen Slots oder Providerrollen.
- `conversation.py`: bestehende HA-Delegation und unveränderte Sicherheitsmechanismen, kein Interpretieren oder Ausführen eigener Tools.
- `migration.py`: isolierte Kenntnis des alten Schemas; nur hier stehen historische Providerrollen und Default-IDs aus 1.0.0.

## Persistiertes Schema

Neue Config Entries verwenden Schema-Version 3, Minor-Version 1. Die normale neue Konfiguration liegt in `options`; `data` ist leer. So bleiben beim späteren Entfernen eines Tokens keine veralteten Kopien in ursprünglichen Setup-Daten zurück. Diese Werte sind Beispielstruktur, keine anzuwendende Konfiguration:

```json
{
  "agents": [
    {
      "entity_id": "conversation.mein_lokaler_agent",
      "enabled": true,
      "health": {
        "kind": "lm_studio",
        "url": "http://modellserver:1234/api/v1/models",
        "timeout": 1.0,
        "cache_seconds": 2.0,
        "failure_cache_seconds": 15.0,
        "expected_status": 200,
        "auth_type": "none",
        "model_key": "exakter/modellschluessel",
        "instance_id": "exakte-instanz",
        "model_state": "loaded"
      }
    },
    {"entity_id": "conversation.anderer_agent", "enabled": true, "health": null}
  ]
}
```

Die Reihenfolge der Liste ist die Priorität. Deaktivierte Einträge verbleiben in der Liste, werden aber vor Entity- und Netzwerkprüfung ausgefiltert. Health-Predicates sind explizit: `loaded` prüft mindestens eine Instanz und optional eine bestimmte ID; `present` verlangt nur das Modellinventar und darf keine Instanz-ID enthalten.

## Migration und Reload

Die Migration vereinigt alte Daten und Optionen, mit Vorrang der Optionen. Sie erzeugt aus den alten drei Rollen drei geordnete aktive Agent-Objekte. Die frühere Health-Prüfung hängt ausschliesslich am früheren lokalen Agent. Erst nach vollständiger Validierung erfolgt ein einzelnes `async_update_entry` mit leeren Daten, neuen Optionen und Schema-Version. Ungültige oder zukünftige Konfiguration wird nicht umgeschrieben.

Entity-Unique-ID und Safety-Ledger bleiben gleich. Bei Options-Reload wird der Health-Manager aus der neuen Konfiguration aufgebaut, damit keine veralteten Bereitschaftsergebnisse oder Zugangsdaten weiterverwendet werden. Unklare und laufende Ausführungen sowie Rückfragebindung bleiben im geteilten Ledger. Eine inzwischen deaktivierte oder entfernte Rückfrage-Entity führt zu keiner Umleitung der Folgeantwort.

## Einen Prüftyp ergänzen

1. In `health_types.py` einen Validator und ein reines Ergebnis-Predicate ergänzen, das `Health(ready, reason)` mit einem inhaltsfreien Fehlercode zurückgibt.
2. `CHECK_TYPES` um `CheckType(reads_json, validate, evaluate, uses_model=False)` erweitern. Transport, Authentifizierung, Cache und Routing bleiben unverändert. `reads_json=False` wertet nur den erfolgreichen HTTP-Status aus; `True` erhält die begrenzte, dekodierte JSON-Antwort.
3. Bei zusätzlichen Konfigurationsfeldern deren validiertes Datenschema und Health-Formular ergänzen; bestehende Modellfelder können über `uses_model=True` wiederverwendet werden. Fehlende Pflichtfelder müssen vor dem Speichern auffallen. Typ- und Feldtexte ergänzen.
4. Predicate-, Transport-, UI-, Cache- und Migrationstests für den neuen Typ ergänzen. Der Test `test_new_adapter_registers_without_routing_changes` demonstriert die Entkopplung.

Neue Typen werden nicht aus fremden Integrationen dynamisch geladen. Das hält den Vertrauens- und Updateumfang klein. Andere Transportprotokolle benötigen einen neuen Transportadapter statt eines HA-Core-Patches.

## Latenz und Grenzen

Prüfungen sind lazy und in Prioritätsreihenfolge. Nach einem Gewinner erfolgt kein Netzwerkkontakt zu niedrigeren Prioritäten. Ohne Prüfkonfiguration wird ausschliesslich die Entity betrachtet. Mehrere erstmals ausgefallene Endpunkte können ihre begrenzten Zeitbudgets addieren; Caches reduzieren dies bei Folgeanfragen. Health-GETs lösen keine Modellinferenz aus.

Eine nach Übergabe erkennbare Störung ist weiterhin kein sicherer Anlass für Wiederholung. Die Integration kennt keine Transaktionsgrenze fremder Agents. Kontextübernahme bleibt durch deren History-Implementierungen und provider-native Inhalte begrenzt. Gesperrte Conversations werden nicht durch Konfigurationsänderungen entsperrt.

## Promptmodus und Zustandsgrenzen ab 1.2

Persistiert werden zusätzlich `prompt: {enabled: false, text: "", reviews: {}}` sowie `prompt_addition: ""` je Agent. Die Migration fügt diese Defaults hinzu, aktiviert nichts und verändert keine anderen Einträge. Die Reviews bilden Entity-ID auf SHA-256 der freigegebenen vollständigen Zielkonfiguration ab.

Der PromptInspector ordnet Entities über Registry und Config-Subentry zu, kontrolliert geladenes Entry-/Subentry-Objekt, gebundene Methoden und Quellhashes. Die Quellenprüfung läuft im HA-Executor; ihr Ergebnis wird für die aktuell geladenen Methoden gecacht. Die Konfigurationsprüfung wird nicht gecacht und benötigt keine Netzwerkabfrage. Vor sowie nach Health-Awaits müssen alle aktiven Ziele die Prüfung bestehen. Unbekannte oder geänderte Ziele blockieren den Gesamtmodus, statt eine andere Priorität zu wählen. Fehlgeschlagene Prüfungen rufen keinen Ziel-Agent auf.

Die statische Zusammensetzung wird pro Options-Reload berechnet: gemeinsamer Text, zwei Newlines, optionale Agent-Ergänzung. Anfragebezogene Extras werden wörtlich mit zwei weiteren Newlines angehängt. Fehlende optionale Teile entfallen. Keine Trims, Jinja-Auswertung, Unicode-Normalisierung, laufende Uhrzeit oder Revisionsmarker in diesen Strings.

Die Revision hasht globalen Text und die aktiven Entity-IDs mit Ergänzung und Reviewhash. Reihenfolge und Health-Parameter ändern sie nicht; Aktivieren/Entfernen von Agents konservativ schon. Bei ausgeschaltetem Modus gilt eine feste Passthrough-Revision. Stale-Status und Revision liegen neben Busy/Blocked/Pending im geteilten Ledger. Revisionwechsel oder abgelehnte Promptprüfung macht die Conversation dauerhaft stale. Safety-Blocked hat Vorrang. Ein Restore auf die frühere Konfiguration entsperrt eine bereits abgewiesene Conversation nicht. Bei neuem Ledger und bestehender Historie wird aktivierter Zusatzmodus ebenfalls abgewiesen.

Promptänderungen während eines bereits gestarteten Zielaufrufs können diesen nicht rückwirkend abbrechen. Ein nachfolgender Turn der bisherigen Conversation wird abgewiesen. Das Ledger wird nicht über HA-Neustarts persistiert; native HA-ChatLogs werden ebenfalls nicht durch den Router rekonstruiert. Es gibt keinen Replay.

Weitere kompatible Promptadapter benötigen identifizierte Registry-/Subentry-Pfade, Transportnachweise mit Tests und eine bewusste Aktualisierung der Quellenfreigabe. Allein eine Domain oder Versionsnummer reicht nicht. Siehe PROMPT_VERWALTUNG.md für die Grenzen externer Tools und Backend-Vorlagen.

## Enge Local-Parameterpolitik ab 1.2.1

`local_parameters.py` ist ein reiner Kompatibilitätsadapter. Nur der Local-Vertrag in `prompt_contracts.json` aktiviert `local_openai_v1`. Er validiert die tatsächlichen Key/Value-Listen, erkennt kleine konstante Literale ohne Jinja-Ausführung und erlaubt nur `reasoning_effort=none` sowie nachweislich deaktiviertes `enable_thinking` im geprüften llama.cpp-Pfad. Der Mixin überschreibt diesen Schalter mit der nativen Option; widersprechende Werte werden abgefangen. Details und HA-String-/Dictionary-Grenzen stehen in PROMPT_VERWALTUNG.md.

Die Politik verändert weder Originalkonfiguration noch Fingerprint-Eingaben. Der vollständige Rohzustand wird vor der Parameterentscheidung wie bisher gehasht. Auch semantisch äquivalente erlaubte Wertänderungen invalidieren Reviews. Keine Cache-Ausnahme, kein normalisierter Ersatz im Hash und kein Providerwissen im Routing. Schema 3.1 und Default-off bleiben unverändert; 1.2.0 ohne Agent-Konfigurationsänderung kann seine vorhandenen Reviews weiterverwenden.
