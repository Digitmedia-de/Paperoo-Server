# Ablauf: Umsetzung am Paperoo-Server

Stand: 2026-11-04. Grundlage ist die Planung in `../../TODO.md` und die Befunde der Sicherheitsprüfung von heute.

Dieses Dokument beschreibt die Reihenfolge der Arbeit am Server. Jeder Schritt hat ein Ziel, die betroffenen Stellen im Code und einen Prüfschritt.

---

## Grundregeln

1. **Eigener Branch und Pull-Request.** Jede Gruppe von Änderungen kommt auf einen eigenen Branch, nie direkt auf `main`.
2. **Changelog pflegen.** Jede Änderung bekommt einen Eintrag in `../CHANGELOG.md` unter „[Unveröffentlicht]“. Bei einer Veröffentlichung wird daraus ein Versionsabschnitt.
3. **Versionen nur patchweise erhöhen.** Von 1.0.0 geht es über 1.0.1 zu 1.0.2. Ein Sprung auf 1.1 oder 2.0 nur auf ausdrückliche Anweisung.
4. **Versionsnummer an drei Stellen pflegen:**
   - `docs/openapi.yaml`, Zeile 29 (`version:`)
   - `docs/README.md`, Abschnitt „Version“
   - `docs/swagger.html`, Anzeige „Version …“
   - Dazu, sobald vorhanden, eine Konstante in `app.py`, die auch in `/api/status` erscheint.
5. **Keine Secrets ins Repo.** `.env`, `*.db` und `logs/` sind in `.gitignore`. Beispielwerte nur in `.env.example`.
6. **Vor dem Commit prüfen:** `git status` darf keine `.env`, keine Datenbank und keine Logdatei zeigen.

---

## Phase 1: Sicherheit (zuerst, Version 1.0.1)

Diese Phase kommt zuerst, weil sie die einzige Lücke mit hohem Risiko schließt.

### 1.1 Route `/print` absichern (Hoch)

- **Problem:** `web_print_todo()` in `app.py` (ca. Zeile 578) hat keinen Schutz. Der Server lauscht auf `0.0.0.0`, also kann jeder im Netz drucken.
- **Änderung:** Den Decorator `@session_manager.require_auth` über die Route setzen, so wie bei den anderen Web-Routen (z. B. `/`).
- **Zusatz:** Die Web-Oberfläche (`templates/index.html`, ca. Zeile 548) sendet ein Formular an `/print`. Ein CSRF-Token wird dort bereits für den Login erzeugt. Für `/print` sollte das Token ebenfalls geprüft werden.
- **Prüfung:**
  - Ohne Anmeldung: `curl -i -X POST http://<server>:<port>/print -d "text=Test"` muss mit 401 oder einer Weiterleitung zum Login antworten, nicht mit einem Druckauftrag.
  - Mit Anmeldung über die Web-Oberfläche: Druck funktioniert wie bisher.

### 1.2 Web-Passwort nur als Hash speichern (Mittel)

- **Problem:** `WEB_PASSWORD` liegt im Klartext in `.env` und wird im Klartext verglichen (`modules/session_manager.py`, `verify_credentials`, Zeile 95).
- **Änderung:**
  - Einen Hash erzeugen: `python3 -c "from werkzeug.security import generate_password_hash as g; print(g('DEIN_PASSWORT'))"`. Das Ergebnis in `.env` als `WEB_PASSWORD_HASH` eintragen.
  - In `SessionManager.__init__` den Hash einlesen. `verify_credentials` nutzt `check_password_hash`.
  - Abwärtskompatibel bleiben: Ist nur `WEB_PASSWORD` gesetzt, läuft der Klartext-Vergleich noch weiter, und beim Start erscheint eine Warnung.
  - `is_enabled()` muss `WEB_PASSWORD_HASH` ebenfalls berücksichtigen.
- **Dateien:** `modules/session_manager.py`, `.env.example`, `docs/README.md` (Hinweis zur Einrichtung).
- **Prüfung:** Anmeldung mit dem richtigen Passwort klappt, mit einem falschen schlägt sie fehl, und die Sperre nach 5 Fehlversuchen greift weiterhin.

### 1.3 API-Key nicht mehr als URL-Parameter (Mittel)

- **Problem:** `modules/auth.py`, Zeilen 39–40, akzeptiert `?api_key=`. Solche Werte landen in Serverlogs und im Browserverlauf.
- **Änderung:** Den Fallback auf `request.args.get('api_key')` entfernen. Erlaubt sind nur `Authorization: Bearer …` und `X-API-Key`.
- **Prüfung:**
  - `curl -i "http://<server>:<port>/api/status?api_key=<KEY>"` muss mit 401 antworten.
  - `curl -i -H "X-API-Key: <KEY>" http://<server>:<port>/api/status` muss mit 200 antworten.
  - Die iOS-App nutzt den Header und ist nicht betroffen.

### 1.4 Restliche Niedrig-Befunde (Niedrig, Version 1.0.2)

- **CORS einschränken:** `app.py`, Zeile 45, `origins: "*"`. Auf die tatsächlich genutzten Herkunftsadressen begrenzen, oder die iOS-App braucht ohnehin keinen CORS-Zugriff. Prüfen, ob die Web-Oberfläche CORS überhaupt benötigt.
- **Login-Sperre über Neustarts:** Die Zähler liegen nur in `SessionManager.login_attempts`. Eine kleine Datei oder die bestehende Datenbank kann sie speichern. Das ist ein eigener, kleiner Schritt.
- **Standard-`SECRET_KEY` entfernen:** `app.py`, Zeile 38. Ohne gesetzten `SECRET_KEY` soll der Server nicht starten, statt mit `dev-secret-key-change-in-production` weiterzulaufen.

### 1.5 Prüfungen ohne Codeänderung

- `pip-audit` mit der `requirements.txt` ausführen und Ergebnisse festhalten.
- Logdateien in `logs/` auf API-Keys und Passwörter durchsuchen, bevor sie weitergegeben werden.

### 1.6 Abschluss Phase 1

- Changelog-Eintrag für 1.0.1 (bzw. 1.0.2) schreiben, Versionsnummer an allen drei Stellen setzen.
- Pull-Request erstellen. Vor dem Merge alle Prüfungen aus 1.1 bis 1.3 wiederholen.

---

## Phase 2: Druck-Typen (Version danach festlegen)

Ziel: Neben dem bisherigen To-do gibt es die Typen Einkaufsliste, Notiz, Zitat, Bild, QR-Code und Quittung für Aufgaben.

### 2.1 Feld `type` in `/api/print`

- `api_print_todo()` in `app.py` (ca. Zeile 338) liest `type` aus dem JSON. Standard ist `todo`. Unbekannte Werte fallen auf `todo` zurück.
- Der Typ wird zusammen mit den bisherigen Metadaten übergeben: `queue_manager.add_todo(text, priority, {'source': 'api', 'language': language, 'type': type})`.
- **Abwärtskompatibilität:** Ohne `type` verhält sich der Aufruf wie bisher. Die bestehende iOS-App bleibt funktionsfähig.

### 2.2 Speicherung in der Warteschlange

- `modules/database.py` speichert `metadata` bereits. Der Typ kann dort hineinwandern, ohne das Tabellenschema zu ändern.
- `modules/print_queue.py`, `add_todo()` (Zeile 94): Metadaten durchreichen, nichts umbauen.
- Beim Verarbeiten der Warteschlange (`_process_queue`, Zeile 36) den Typ auslesen und an den Drucker weitergeben.

### 2.3 Formatierung je Typ

- `modules/printer_manager.py`: `print_todo()` (Zeile 116) und `_format_and_print()` (Zeile 220) sind auf To-dos zugeschnitten.
- Vorschlag: `_format_and_print()` bleibt für `todo`. Für die anderen Typen je eine Funktion, z. B. `_format_list()`, `_format_note()`, `_format_quote()`, `_format_receipt()`, `_format_image()`, `_format_qr()`.
- Gemeinsame Teile wie Zeilenumbruch (`_wrap_text_centered`) und Trennlinien werden wiederverwendet, nicht kopiert.
- **Einkaufsliste:** Listenname als Überschrift, dann die Einträge mit Kästchen.
- **Notiz:** Text linksbündig, Datum oben.
- **Zitat:** Text zentriert mit Autor, falls angegeben.
- **Quittung für Aufgaben:** Aufgaben mit Häkchen, Summe unten.
- **Bild:** Pillow öffnet das Bild, skaliert auf die Bonbreite und wandelt es in Schwarzweiß um. Die Umsetzung über `python-escpos` (`printer.image()`) ist zu prüfen, da sie je nach Drucker abweicht.
- **QR-Code:** `python-escpos` bringt `qr()` mit. Für WLAN-Zugang wird ein Standardformat verwendet (`WIFI:T:WPA;S:<SSID>;P:<Passwort>;;`).

### 2.4 Prüfung Phase 2

- Unit-Tests für die Formatierung mit einem Testdrucker (Dummy-Backend von `python-escpos`), ohne echte Hardware.
- Manuelle Prüfung am echten Drucker für jeden Typ, Ergebnis im Changelog festhalten.
- Beispielaufrufe:
  ```bash
  curl -X POST http://<server>:<port>/api/print \
    -H "X-API-Key: <KEY>" -H "Content-Type: application/json" \
    -d '{"type":"list","text":"Milch\nBrot\nEier","priority":3}'
  ```

---

## Phase 3: Motivationssprüche mit mehreren Anbietern

- **Ist-Zustand:** `modules/motivation_generator.py` spricht fest `https://api.openai.com/v1/chat/completions` an (Zeile 75). Der Schlüssel und das Modell kommen nur aus `.env`.
- **Ziel:** Anbieter wählbar in `.env` und in der Web-Oberfläche: OpenAI, Anthropic, OpenRouter und ein lokales LLM (OpenAI-kompatibel, z. B. Ollama oder LM Studio).
- **Umsetzung:**
  - Eine Konfiguration `MOTIVATION_PROVIDER` mit den Werten `openai`, `anthropic`, `openrouter`, `local`.
  - Je Anbieter Basis-URL, Schlüssel und Modell. Für `local` nur die Basis-URL.
  - Anthropic nutzt eine eigene API (Messages API, Header `x-api-key`). Die anderen drei sind OpenAI-kompatibel, daher reicht ein gemeinsamer Aufruf mit anderer Basis-URL.
  - Die Texte in `modules/translations.py` (`motivation_subtitle`, Zeilen 23 und 93) nennen dann keinen festen Anbieter mehr.
- **Sicherheit:** Schlüssel nie in Logs ausgeben. Bei einem Fehler nur Statuscode und Anbieter loggen.
- **Prüfung:** Für jeden Anbieter ein Testaufruf, bei Fehlern kommt der Standardtext, der Druck läuft weiter.

---

## Phase 4: Spätere Punkte (noch nicht entschieden)

- **Warteschlange in der Oberfläche steuern** (ansehen, wiederholen, leeren). Die Endpunkte unter `/api/queue/*` existieren bereits. Erst entscheiden, ob das in der Web-Oberfläche, in der iOS-App oder in beiden passieren soll.
- **Ideen** aus `../../TODO.md` (Tagesbriefing, Home-Assistant-Anbindung, Fotos, Barcode-Etiketten, Wochenplan). Noch nicht bewertet.

---

## Checkliste für jede Änderung

- [ ] Branch angelegt, nicht auf `main` gearbeitet
- [ ] Changelog-Eintrag unter „[Unveröffentlicht]“ ergänzt
- [ ] Versionsnummer nur patchweise erhöht und an allen drei Stellen gesetzt
- [ ] `git status` ohne `.env`, Datenbank oder Logs
- [ ] Prüfschritte der betroffenen Phase durchgeführt und Ergebnisse notiert
- [ ] `docs/openapi.yaml` angepasst, wenn sich die API ändert
