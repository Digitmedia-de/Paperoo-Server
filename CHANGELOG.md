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

### Geplant
- Abhängigkeitsupdates nach dem Sicherheitsaudit: Flask 3.1.3, python-dotenv 1.2.2, Werkzeug 3.1.9, Pillow 13.0.0 und requests 2.33.0.
- Druck-Typen über ein Feld `type` (Standard `todo`): Einkaufsliste, Notiz, Zitat, Bild, QR-Code, Quittung für Aufgaben
- Motivationssprüche: Anbieter wählbar (OpenAI, Anthropic, OpenRouter, lokales LLM)

### Stand 2026-11-04
- Phase 1 aus `docs/ablauf-server.md` umgesetzt.
- Verhalten mit Flask-Routenaufrufen und echten HTTP-`curl`-Aufrufen geprüft; die Druckhardware wurde dabei durch ein Testdouble ersetzt.
- `pip-audit`: 85 Rohmeldungen beziehungsweise 61 eindeutige paketbezogene IDs in fünf bereits angepinnten Abhängigkeiten; Updates sind noch nicht durchgeführt.
- `logs/` war bei der Prüfung auf Zugangsdaten leer.

## [1.0.0]

- Ausgangsstand laut Dokumentation (`docs/openapi.yaml`, `docs/README.md`).
