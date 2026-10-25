# Originalgrafik Assist Router

Eigenständiges flaches Symbol: Eine Sprechblase verbindet einen Eingangs-Knoten mit drei Routing-Zielen. Keine HA-Hausform, kein HA-Logo und keine Logos von OpenAI, Gemini, Gemma oder LM Studio. Die drei gezeichneten Abzweige symbolisieren Routing, keine technische Beschränkung auf drei Agents. Eigene Grafik unter MIT, nicht als offizielles HA-Projekt ausgeben.

SVG-Quellen: [hell](../assets/icon.svg), [dunkel](../assets/dark_icon.svg). SVG ist editierbares Original-/Dokumentationsmaterial; HA erhält PNG. Lokale Einbindung ohne Pythonänderung über custom_components/assist_router/brand/icon.png und icon@2x.png, zusätzlich dark_icon.png und dark_icon@2x.png. 256×256 bzw. 512×512, RGBA, transparente Aussenbereiche, quadratisch und auf den sichtbaren Umriss beschnitten; keine externe Schrift, Grafik oder Netzwerkreferenz. Eine separate breite Logo-Datei ist für diese quadratische Marke nicht erforderlich.

Reproduzieren: `python tools/generate_brand.py` (Pillow nur Entwicklungsabhängigkeit). Die PNGs wurden visuell auf hellem/dunklem Hintergrund und strukturell auf Format, Abmessungen und Alpha geprüft.

[Offizielle HA-Vorgaben](https://contributors.home-assistant.io/core/integrations/brands/), geprüft 25.10.2026: Custom Integrations können seit HA 2026.3 lokale brand/-Bilder liefern. Diese haben Vorrang vor zentralen Bildern. Eigene Custom Integrations dürfen keine Home-Assistant-Markenbilder verwenden. Hier genügt der lokale Pfad; kein externer Brands-PR und kein Anspruch auf offizielle Anerkennung. [HACS verlangt mindestens ein lokales icon.png](https://www.hacs.xyz/docs/publish/integration/). Die Laufzeit-Zielversion 2026.10.2 unterstützt diesen Weg; die tatsächliche Frontendanzeige ist erst im Ziel-HA abzunehmen.
