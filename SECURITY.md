# Sicherheit

Assist Router 1.2.1 delegiert an vorhandene Agents und kann dadurch reale Aktionen auslösen. Kein automatischer Zweitaufruf nach unklarem Ausgang. Keine Exactly-once-Garantie fremder SDKs oder Werkzeuge. Der zentrale Promptmodus bleibt additiv; die Quellen-/Fingerprintprüfung wird durch die HACS-Vorbereitung nicht gelockert.

Keine API-Schlüssel, HA-Config-Entry-Exporte, Systemprompts, Toolargumente oder privaten URLs in öffentliche Issues aufnehmen. Sicherheitslücken später über GitHubs private Vulnerability Reporting melden, sofern der Maintainer diese Funktion freigeschaltet hat; andernfalls zuerst ein inhaltsarmes Kontakt-Issue ohne Exploit oder Geheimnisse erstellen. Die Funktion wird durch diese lokale Vorbereitung nicht aktiviert.

Die lokale Hygieneprüfung und Gitleaks verwenden keine produktiven Tokens. CI nutzt ausschliesslich den automatisch von GitHub bereitgestellten kurzlebigen Token für lesende Repositoryprüfungen. Secret-Scanning/Push-Protection auf GitHub sind zusätzlich nach Repositoryerstellung bewusst zu aktivieren. Kein Scan garantiert die Abwesenheit sämtlicher Geheimnisse.

Für die Erstveröffentlichung ausschliesslich den freigegebenen Publikationsumfang committen. Kein Upload eines übergeordneten Arbeitsverzeichnisses. Bei tatsächlichem Tokenfund Token zuerst sperren/rotieren und Historie gesondert untersuchen; nicht nur die Warnung unterdrücken.
