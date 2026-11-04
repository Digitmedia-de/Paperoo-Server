# Changelog – Paperoo-Server

Alle nennenswerten Änderungen am Server werden hier festgehalten.
Versionierung: nur die letzte Stelle wird erhöht (z. B. 1.0.1 → 1.0.2), außer es wird ausdrücklich etwas anderes vereinbart.

## [Unveröffentlicht]

### Dokumentation
- `README.md`: Installationsbefehl zeigt auf das korrekte Repository `Digitmedia-de/Paperoo-Server`.
- `README.md`: Installationspfad ist jetzt `/opt/Paperoo-Server` (bisher `/opt/paperoo`), auch in der systemd-Unit. Grund: Auf dem Gerät liegt der Ordner unter diesem Namen.

### Sicherheit (Version 1.0.1)
- `POST /print` erfordert eine angemeldete Websession und ein gültiges CSRF-Token.
- Die Weboberfläche unterstützt `WEB_PASSWORD_HASH` mit Werkzeug-Hashes; `WEB_PASSWORD` bleibt als Klartext-Fallback mit Startwarnung kompatibel.
- API-Keys werden nur noch über `Authorization: Bearer …` oder `X-API-Key` akzeptiert, nicht mehr als URL-Parameter.

### Sicherheit (Version 1.0.2)
- Die pauschale CORS-Freigabe wurde entfernt; Weboberfläche und API verwenden dieselbe Herkunft.
- Fehlgeschlagene Login-Versuche und die Sperre nach fünf Versuchen werden in SQLite gespeichert und bleiben über Neustarts erhalten.
- Ohne gesetzten `SECRET_KEY` verweigert der Server den Start.
- `GET /api/status` meldet die Serverversion.

### Druck-Typen (Version 1.0.3)
- `POST /api/print` akzeptiert `type` mit `todo`, `list`, `note`, `quote`, `image`, `qr` und `receipt`; fehlende und unbekannte Werte bleiben kompatibel zu `todo`.
- Listen unterstützen einen Titel, Zitate einen Autor und Bilder Base64-Daten. Bilder werden auf die Bonbreite skaliert und in Schwarzweiß umgewandelt.
- Warteschlange und Wiederholungen geben Typ und Metadaten vollständig an den Druckformatierer weiter.

### Motivation und Abhängigkeiten (Version 1.0.4)
- Motivationssprüche sind mit OpenAI, Anthropic, OpenRouter und lokalen OpenAI-kompatiblen LLMs möglich.
- Anbieter, Aktivierung, Basis-URLs und Modelle sind konfigurierbar; Anbieter und Aktivierung können in der Weboberfläche geändert werden.
- Flask 3.1.3, python-dotenv 1.2.2, Werkzeug 3.1.9, Pillow 13.0.0 und requests 2.33.0 schließen die gemeldeten Abhängigkeitsbefunde. Python 3.11 ist nun die Mindestversion.

### Systemupdates (Version 1.0.5)
- `update.sh --check` vergleicht lokale Version und Commit mit `origin/main`; `update.sh --install` installiert Fast-forward-Updates.
- Vor der Installation werden `.env` und SQLite gesichert. Abhängigkeiten, Syntax und optionale Migrationen werden geprüft, bei Fehlern erfolgt ein Code-Rollback.
- Die Weboberfläche bietet Updateprüfung, Installation und Jobstatus; alle schreibenden Endpunkte sind durch Session und CSRF geschützt.
- Der Fallback des Installers berücksichtigt nun auch `requests`, sodass `motivation_generator.py` nach einer Einzelpaketinstallation startet.

### Stand 2026-11-04
- Phasen 1 bis 3 aus `docs/ablauf-server.md` umgesetzt.
- Verhalten mit Flask-Routenaufrufen und echten HTTP-`curl`-Aufrufen geprüft; die Druckhardware wurde dabei durch ein Testdouble ersetzt.
- Das ursprüngliche `pip-audit` meldete 61 eindeutige paketbezogene IDs; nach den Updates werden keine bekannten Lücken mehr gemeldet.
- `logs/` war bei der Prüfung auf Zugangsdaten leer.

## [1.0.0]

- Ausgangsstand laut Dokumentation (`docs/openapi.yaml`, `docs/README.md`).
