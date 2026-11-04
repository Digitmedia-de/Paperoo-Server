# Paperoo API Dokumentation

## 📚 Übersicht

Diese Dokumentation beschreibt die REST API von Paperoo. Die API ermöglicht es, Aufgaben auf Bondruckern auszugeben und die Druckwarteschlange zu verwalten.

## 🌐 Zugriff auf die Dokumentation

### Online Swagger UI
Öffnen Sie in Ihrem Browser:
```
http://localhost:5001/docs
```

### Lokale HTML-Dokumentation
Öffnen Sie die Datei `swagger.html` direkt in Ihrem Browser.

## 📁 Dateien

- **openapi.yaml** - OpenAPI 3.0 Spezifikation der API
- **swagger.html** - Interaktive HTML-Dokumentation mit Swagger UI
- **README.md** - Diese Datei

## 🔧 API Spezifikation

Die API-Spezifikation liegt im OpenAPI 3.0 Format vor und kann:
- In Swagger UI angezeigt werden
- In Postman importiert werden
- Für Code-Generierung verwendet werden
- Als Referenz für Entwickler dienen

## 🚀 Schnellstart

### 1. API-Key erhalten
Der API-Key wird bei der Installation generiert und ist in der `.env` Datei gespeichert.

### 2. Erste Anfrage
```bash
curl -X POST http://localhost:5001/api/print \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"text": "Meine erste Aufgabe", "priority": 3}'
```

### 3. Status prüfen
```bash
curl -X GET http://localhost:5001/api/status \
  -H "Authorization: Bearer your-api-key"
```

## 📋 Verfügbare Endpunkte

### Drucken
- `POST /api/print` - To-do, Einkaufsliste, Notiz, Zitat, Bild, QR-Code oder Aufgabenquittung drucken

Das optionale Feld `type` akzeptiert `todo` (Standard), `list`, `note`, `quote`, `image`, `qr` und `receipt`. Unbekannte Werte fallen auf `todo` zurück. Listen und Quittungen lesen ihre Einträge zeilenweise aus `text`; Zitate akzeptieren `author`, Listen `title` oder `list_name`. Bilder werden als Base64 in `image` übertragen und benötigen keinen `text`.

### Einstellungen
- `POST /api/settings/motivation` - KI-Anbieter und Aktivierung über die Weboberfläche einstellen (Websession und `X-CSRF-Token` erforderlich)

### Systemupdates
- `GET /api/system/update/status` - installierte Version und letzten Update-Job lesen
- `POST /api/system/update/check` - lokale Version und Commits mit `origin/main` vergleichen
- `POST /api/system/update/install` - Backup und Fast-forward-Update im Hintergrund starten

Die POST-Endpunkte benötigen Websession und `X-CSRF-Token`. Auf der Kommandozeile stehen ebenfalls `./update.sh --check` und `./update.sh --install` zur Verfügung. `--install --no-restart` installiert ohne Service-Neustart.

### Warteschlange
- `GET /api/queue/status` - Warteschlangen-Statistiken
- `GET /api/queue/todos` - Letzte Aufgaben
- `GET /api/queue/pending` - Wartende Aufgaben
- `POST /api/queue/retry` - Fehlgeschlagene wiederholen

### Status
- `GET /api/status` - System- und Druckerstatus
- `GET /health` - Health Check (ohne Auth)

## 🔐 Authentifizierung

Die API akzeptiert Bearer Token oder den `X-API-Key`-Header. API-Keys werden nicht als URL-Parameter akzeptiert:

```
Authorization: Bearer your-api-key-here
X-API-Key: your-api-key-here
```

Für die Web-Anmeldung sollte das Passwort als Werkzeug-Hash in `WEB_PASSWORD_HASH` gespeichert werden:

```bash
python3 -c "from werkzeug.security import generate_password_hash as g; print(g('DEIN_PASSWORT'))"
```

Das bisherige `WEB_PASSWORD` bleibt als Klartext-Fallback mit Startwarnung kompatibel. Zusätzlich muss `SECRET_KEY` gesetzt sein; ohne diesen Wert startet der Server nicht.

## 🌍 Mehrsprachigkeit

Die API unterstützt Deutsch und Englisch. Die Sprache kann pro Anfrage festgelegt werden:

```json
{
  "text": "Complete documentation",
  "priority": 4,
  "language": "en"
}
```

## 📊 Response Format

Alle API-Antworten folgen diesem Format:

```json
{
  "success": true|false,
  "message": "Statusnachricht",
  "data": { ... }
}
```

Bei Fehlern:
```json
{
  "success": false,
  "error": "Fehlerkategorie",
  "message": "Detaillierte Fehlermeldung"
}
```

## 🛠️ Tools und Integration

### Postman
1. Importieren Sie die `openapi.yaml` Datei in Postman
2. Erstellen Sie eine Environment-Variable für den API-Key
3. Testen Sie die Endpunkte

### Code-Generierung
Die OpenAPI-Spezifikation kann zur Generierung von Client-Libraries verwendet werden:
- JavaScript/TypeScript
- Python
- Go
- Java
- Swift

### Beispiel: Python Client
```python
import requests

API_KEY = "your-api-key"
BASE_URL = "http://localhost:5001"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Aufgabe drucken
response = requests.post(
    f"{BASE_URL}/api/print",
    headers=headers,
    json={
        "text": "Python Test",
        "priority": 4,
        "language": "de"
    }
)

print(response.json())
```

## 📝 Änderungsprotokoll

### Version 1.0.5
- Lokale und GitHub-Versionsprüfung über `update.sh`
- Backup, Fast-forward-Update, Abhängigkeitsinstallation und Service-Neustart
- Update-Bereich in der Weboberfläche mit Session- und CSRF-Schutz

### Version 1.0.4
- OpenAI, Anthropic, OpenRouter und lokale LLMs für Motivationssprüche
- Anbieterwahl in der Weboberfläche
- Aktualisierte Abhängigkeiten ohne bekannte `pip-audit`-Befunde; Python 3.11 oder neuer erforderlich

### Version 1.0.3
- Druck-Typen To-do, Einkaufsliste, Notiz, Zitat, Bild, QR-Code und Aufgabenquittung
- Typ und Zusatzdaten werden auch bei Warteschlangen-Wiederholungen übernommen

### Version 1.0.2
- Pauschale CORS-Freigabe entfernt
- Login-Sperre bleibt über Server-Neustarts erhalten
- `SECRET_KEY` ist für den Serverstart erforderlich
- Serverversion in `GET /api/status`

### Version 1.0.1
- Webdruck mit Session- und CSRF-Schutz
- Unterstützung für `WEB_PASSWORD_HASH`
- API-Key nur noch per `Authorization`- oder `X-API-Key`-Header

### Version 1.0.0
- Initiale API-Version
- Basis-Endpunkte für Druck und Warteschlange
- Bearer Token Authentifizierung
- Mehrsprachige Unterstützung

## 🆘 Support

Bei Fragen oder Problemen:
1. Prüfen Sie die interaktive Dokumentation unter `/docs`
2. Schauen Sie in die Logs unter `logs/`
3. Erstellen Sie ein Issue auf GitHub