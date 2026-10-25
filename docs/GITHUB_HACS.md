# GitHub/HACS: Assist Router 1.2.1

## Publikationsstatus und Layout

Nur lokale Vorbereitung am 25. Oktober 2026. Öffentliches **Ziel**: BugsDan/ha-assist-router. Kein Repository, Commit, Tag, Release, Brands-PR oder produktiver Codewechsel wird durch diese Dateien erstellt. Das vorhandene Schwesterprojekt BugsDan/ha-yuvomi-mcp wurde als Struktur-/Workflowvorbild gelesen, nicht verändert.

Das Publikations-ZIP hat den Repository-Stamm direkt an der ZIP-Wurzel: README, LICENSE, hacs.json, .github/, custom_components/assist_router, Tests, Werkzeuge und lizenzierte Referenzen. Es ist **kein** ZIP zum vollständigen Entpacken in HA. Das separate public-baseline-Installations-ZIP enthält den Code unter custom_components/assist_router. Auch daraus nur diesen Integrationsordner nach HA kopieren.

HACS: content_in_root=false, zip_release=false, hide_default_branch=true, minimale HA-Version 2026.10.2. HACS bezieht die Integration aus dem Quellbaum eines veröffentlichten Release-Tags. Ein ZIP-Asset mit flacher Struktur wird nicht erwartet. Kein persistent_directory: persistente Routeroptionen liegen im normalen HA-Config-Entry-Speicher ausserhalb des Codes.

## Späterer Erst-Upload – nur nach ausdrücklicher Freigabe

1. Öffentlichen Repositorynamen BugsDan/ha-assist-router, Beschreibung „Configurable Home Assistant Assist conversation routing with conservative fallback and shared prompt additions.“, Topics home-assistant, hacs, assist, conversation, custom-integration setzen. Issues einschalten. Beschreibung/Topics sind GitHub-Einstellungen und nicht durch lokale Metadaten bereits gesetzt.
2. Nur den geprüften Publikationsumfang übernehmen. Vor Commit `git diff --cached` vollständig prüfen; lokale Hygiene-/Gitleaks-Scans ausführen. Keine Parent-Workspace- oder privaten HA-Daten in die Git-Historie aufnehmen.
3. Nach späterem Push alle GitHub-Checks abwarten: Quellenverträge/Tests, echte Linux-HA-Tests, Secret-Scan mit Historie, HACS und hassfest. Repositoryseitige Validierung kann vor öffentlicher Repositoryerstellung nicht vollständig lokal nachgebildet werden. Kein ignore für Brands, Lizenz oder Topics konfigurieren, nur damit ein Check grün wird.
4. Erst auf dem geprüften Commit ein erstes Tag **v1.2.1** erstellen; Versionen in Manifest/const/Projekt bleiben **1.2.1**. Bereits das Pushen eines Tags ist eine Veröffentlichungshandlung und findet jetzt nicht statt.
5. Ein GitHub-Release **v1.2.1** mit docs/RELEASE_1.2.1.md vorbereiten, ZIPs/Prüfsummen bewusst prüfen und erst nach Freigabe veröffentlichen. Keine Actions führen diesen Schritt automatisch aus. Veröffentlichte Tags/Assets später nicht still verschieben oder ersetzen.
6. Als benutzerdefiniertes HACS-Repository testen. HACS-Standardkatalogaufnahme ist ein separater Antrag, keine Voraussetzung für diesen Weg.

## Bestehende manuelle 1.2.1-Installation übernehmen

1. Vollständiges HA-Backup samt `.storage` und bisherigem Integrationscode sichern. Zusätzliche Codekopie ausserhalb custom_components ablegen. Laufende Anfragen beenden; bei unklarem Ausgang den tatsächlichen Gerätezustand bzw. Listeneintrag prüfen. Ein Neustart löscht die nur im RAM gehaltenen Safety-Sperren und ist kein sicherer Retry.
2. Bestehenden **assist_router Config Entry behalten**: nicht entfernen, nicht neu anlegen, Entry-ID/Domain/Entity-ID nicht ändern. Keine .storage-Dateien manuell editieren. Der zentrale Prompt, Ergänzungen, Aktivierung, Reihenfolge, Agentfreigaben und Health-Konfiguration inklusive Zugangsdaten gehören zu dessen Daten/Optionen, nicht zu README oder Pythondateien.
3. Nach späterer Veröffentlichung in HACS das Ziel-Repository als Typ Integration hinzufügen. **Assist Router 1.2.1 erneut herunterladen.** HACS entdeckt manuelle Installationen nicht automatisch zuverlässig; das erneute Herunterladen stellt die Codeverwaltung her. Keine zweite Integration hinzufügen.
4. HACS darf Code unter `/config/custom_components/assist_router` ersetzen, nicht den Config Entry löschen. Falls HACS einen bestehenden Ordner ablehnt: stoppen, Backup prüfen und konkrete Fehlermeldung klären. Keine Entry-/Storage-Löschung als Umgehung. Kein Backupordner als zweite Integration unter custom_components.
5. HA neu starten. Exakt gleiche Entry-ID, bestehende Router-Entity und Assist-Pipeline prüfen; **Befehle bevorzugt lokal verarbeiten** bleibt aktiv. Promptmodus/-text, Ergänzungen, geordnete Agentliste, aktive/deaktivierte Agents, Review-Fingerprints und Health-Einstellungen vergleichen, ohne geheime Daten zu veröffentlichen.
6. Eine **neue Conversation** beginnen. Alte ChatLogs/offene Rückfragen werden beim HA-Neustart nicht durch HACS migriert. Der Patch verändert weder Ziel-Agent-Konfigurationen noch die Promptquellenfreigabe; bei identischen Zielintegrationen bleiben die gespeicherten Fingerprints gültig. Haben sich die Agents unabhängig geändert, ist deren erneute Prüfung sachlich erforderlich – nicht den Routercheck abschalten.
7. Zunächst eine harmlose Anfrage ohne Schreibwerkzeuge, danach kontrollierte Abnahme mit isolierten Testdaten. Kein produktives Einkaufskommando zum blinden Wiederholen verwenden. HACS muss den Router als heruntergeladen in Version 1.2.1 führen.

Bis auf die explizit dokumentierte Bereinigung des fehlenden Legacy-URL-Fallbacks ist der funktionale Code unverändert; die konkrete HACS-Übernahme und Linux-HA-Abnahme bleiben reale, erst später auszuführende Schritte. Die Vorbereitung selbst hat keine HA-Installation verändert. Für 1.1.0 bleibt die vorhandene Schema-Migration unverändert; für 1.0.0 gilt der folgende explizite Endpunktnachweis; der reine Wechsel 1.2.1 → öffentliche 1.2.1 benötigt keine neue Datenmigration (Schema unverändert 3.1).

## Einziger Legacy-Sonderfall: 1.0.0 ohne gespeicherte URL

Die Bereinigung entfernt den alten privaten Fallback ausschliesslich aus der 1.0-Schema-Migration. Ein vorhandener, gültiger Wert `models_url` wird **exakt übernommen**, auch wenn er auf einen privaten LAN-Host oder Reverse-Proxy zeigt. Optionen behalten ihren Vorrang vor Daten. Modell-/Instanzkennung, Zugangsdaten und Zeitbudgets werden unverändert übernommen; keine Netzwerkprobe oder Agent-Konfiguration wird dadurch verändert.

Fehlt `models_url` oder ist der gespeicherte Wert ungültig, wird die Migration vor jedem Schreibzugriff abgelehnt. Kein Ersatzhost, kein Wechsel auf Cloud, keine still entfernte Health-Prüfung und keine Credential-Weitergabe an ein neues Ziel. Der alte Config Entry bleibt unverändert. Eine implizite private Adresse lässt sich nach deren Entfernung ohne gespeicherte Information nicht zuverlässig rekonstruieren.

Wer tatsächlich noch so einen 1.0-Eintrag verwendet, sollte **vor** dem HACS-Wechsel mit seinem gesicherten bisherigen 1.0-Code im vorhandenen Konfigurationsdialog den tatsächlichen vollständigen Health-Endpunkt ausdrücklich speichern und danach das Backup aktualisieren. Anschliessend denselben Config Entry behalten und erneut übernehmen. Falls die Migration bereits mit Fehler gestoppt hat, zuerst den gesicherten bisherigen Code wiederherstellen, URL dort bewusst speichern, dann erneut versuchen. Keine .storage-Manipulation, kein Löschen/Neuanlegen des Entries und kein geratener URL-Wert als Abkürzung.

Aktuelle 1.2.x-Einträge verwenden bereits Schema 3.1 und speichern Health-Endpunkte je Agent. Sie werden durch diese Bereinigung nicht umgeschrieben. Zentraler Prompt, Ergänzungen, Agentenreihenfolge, Aktivierung, Review-Fingerprints und Health-Einstellungen bleiben exakt erhalten; auch die gespeicherte Promptrevision hat bei unveränderten Werten denselben Wert. Der Wechsel auf HACS benötigt für diese bestehenden Daten keine neue Freigabe. Unabhängig geänderte Ziel-Agent-Konfigurationen lösen wie bisher eine neue Prüfung aus.

## Rollback

Bei einer fehlgeschlagenen Codeübernahme den gesicherten ursprünglichen **1.2.1-Code** am gleichen Pfad wiederherstellen und HA neu starten. Config Entry dabei beibehalten. Bei tatsächlichem Konfigurationsverlust das vollständige zusammenpassende HA-Backup wiederherstellen, keine Fragmente in .storage zusammenmischen. Ein Downgrade auf 1.1.0 ist ein anderer Vorgang: Schema 3 ist dort unbekannt und benötigt das passende ältere Backup. Keine Wiederholung unklarer Aktionen durch einen Rollback auslösen.

## Offizielle Quellen, geprüft 25.10.2026

- [HACS Integration-Layout und lokale Brand-Assets](https://www.hacs.xyz/docs/publish/integration/)
- [hacs.json und veröffentlichte Releases](https://www.hacs.xyz/docs/publish/start/)
- [HACS: vorhandene manuelle Elemente erneut herunterladen](https://www.hacs.xyz/docs/faq/existing_elements/)
- [HACS Validierungsaction](https://www.hacs.xyz/docs/publish/action/)
- [Home Assistant: lokale Brand-Bilder](https://contributors.home-assistant.io/core/integrations/brands/)
