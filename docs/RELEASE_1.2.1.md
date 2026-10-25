# Assist Router 1.2.1 – erste öffentliche Baseline (Entwurf)

Geplantes Repository: BugsDan/ha-assist-router. Vorgesehenes Tag: v1.2.1. Noch nicht erstellt oder veröffentlicht.

- Bestehende Funktion aus der manuell ausgelieferten Version 1.2.1 unverändert übernommen: generische geordnete Agents, Health-Checks, konservatives Routing, Kontext und optionale zentrale Prompt-Zusätze mit Quellen-/Fingerprintprüfung.
- Repository-/Maintainer-Metadaten, HACS-Layout und lokale Original-Icons vorbereitet. Einzige notwendige Funktionsbereinigung: alte 1.0-Migration verlangt einen gespeicherten gültigen Health-Endpunkt statt einer privaten Default-URL; bei Fehlen atomarer Abbruch ohne Änderungen.
- Tests, HACS-/hassfest-/Secret-Scan-Workflows, Lizenzabgrenzung und sichere manuell-zu-HACS-Übernahme dokumentiert.
- Keine automatische Health-Erkennung hinzugefügt; Roadmap dokumentiert.

Version, Domain assist_router, Config-Entry-Schema 3.1 und alle übrigen funktionalen Integrationsdateien bleiben erhalten. Explizite bestehende Endpunkte werden nicht verändert; aktuelle Config Entries benötigen keine neue Datenmigration. Bestehende Installation nicht löschen oder neu konfigurieren. HACS soll lediglich den gleichen Codepfad verwalten; Details in GITHUB_HACS.md. Vor HA-Neustart laufende/unklare Aktionen prüfen; RAM-Safety-Ledger und ChatLogs sind keine persistente Migration.

Vor einer späteren Veröffentlichung echte Linux-HA-Tests, HACS und hassfest auf GitHub abwarten. Die lokale Review-Zusammenfassung ersetzt keine grünen Remotechecks. Keine automatische Veröffentlichung durch vorbereitete Workflows.
