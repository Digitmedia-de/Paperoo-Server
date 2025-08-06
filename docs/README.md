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
- `POST /api/print` - Neue Aufgabe drucken

### Warteschlange
- `GET /api/queue/status` - Warteschlangen-Statistiken
- `GET /api/queue/todos` - Letzte Aufgaben
- `GET /api/queue/pending` - Wartende Aufgaben
- `POST /api/queue/retry` - Fehlgeschlagene wiederholen

### Status
- `GET /api/status` - System- und Druckerstatus
- `GET /health` - Health Check (ohne Auth)

## 🔐 Authentifizierung

Die API verwendet Bearer Token Authentifizierung:

```
Authorization: Bearer your-api-key-here
```

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