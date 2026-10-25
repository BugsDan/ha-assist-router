# Spätere Verbesserungen – nicht in 1.2.1 implementiert

## Automatische Vorschläge für Health-Checks

Ziel: aus eindeutig identifizierten vorhandenen Agents lesende Health-Vorschläge ableiten, die der Nutzer im Routerdialog prüft. Keine heimliche Änderung von Endpunkten, Zugangsdaten, Zielintegrationen oder Freigaben. Manuell konfigurierte Checks behalten Vorrang und bleiben an die Entity-ID gebunden. Als getrenntes, getestetes späteres Release behandeln.

- LM Studio: OpenAI-Inferenzbasis typischerweise `http://lmstudio.example:1234/v1`, Modell-Inventar/-Ladezustand über `http://lmstudio.example:1234/api/v1/models`. Pfade sind unterschiedliche APIs; Reverse-Proxy-Präfixe respektieren. Nicht `/v1/api/v1/models` anhängen und nicht beliebig Query/Fragmente übernehmen.
- Generische OpenAI-kompatible APIs: `/v1/models` kann nur Modell-IDs/Inventar oder sogar statische Anbieterlisten liefern. Das beweist weder geladenes Modell noch freie Inferenzslots. Keine lokale Ladebereitschaft aus einem HTTP-200 oder Modellnamen erfinden. Bei OpenAI Cloud existiert keine mit LM Studio gleichzusetzende lokale loaded_instances-Semantik.
- Fähigkeitsabhängige Ergebnisse unterscheiden: `available/present`, `loaded`, `unknown`, `unreachable`. Nur ein geeigneter, dokumentierter Adapter darf `loaded` behaupten. Falsches Modell, leere loaded_instances und unpassende Instanz müssen negativ sein. Unbekannter Zustand ist kein positiver Loaded-Nachweis.
- Endpunkt-Plausibilität vor Probe-GET prüfen: HTTP(S), Host/Port/Pfad, keine eingebetteten Credentials/Fragmente, keine unerwarteten Redirects oder fremden Hosts; unerwünschte lokale Metadata-/Loopback-Ziele gesondert betrachten. Auth nur an den bewusst bestätigten Ursprung senden. Inferenz-, Chat- und Tool-Endpunkte nicht als Healthprobe verwenden. Auch ein Syntaxcheck ersetzt keinen Fähigkeitsnachweis.
- Vorschläge verwenden keine globalen Providerrollen. Modell-/Instance-ID eindeutig aus unterstütztem Konfigurationsschema ableiten oder im UI erfragen; keine Entity-ID als Modellschlüssel interpretieren. Zugangsdaten nicht in Diagnosen/Formularvorgaben spiegeln und keine Codes automatisch an andere Hosts kopieren.
- Kurze Gesamt-/Verbindungsbudgets und positive/negative Caches beibehalten. Keine periodischen Hintergrundprobes oder Modellladeaktionen ohne separate bewusste Funktion.

Abnahmetests eines späteren Releases: verschiedene Basis-/Proxy-URLs, generisches Model-Inventar ohne Ladeinformation, lokal vorhanden aber ungeladen, mehrere Instanzen, falscher Schlüssel, 401/403/404/Redirect, TLS-/Timeoutfehler, Auth-Ursprungsbindung sowie Unicode-Modellnamen. Nach Übergabe an einen Agent bleibt konservativer No-Retry unverhandelbar. Eine Health-Änderung ist kein Anlass, alte unklare Aktionen zu wiederholen.

**Aktuell 1.2.1:** Optionale explizite HTTP- und LM-Studio-Checks bleiben unverändert. `loaded`/`present` sind bereits manuell wählbar; automatische Ableitung und neue Provider-Adapter werden hier nur geplant.
