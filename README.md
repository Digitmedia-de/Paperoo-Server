# Paperoo 🎯

Ein intelligenter Aufgaben-Manager mit Bondruckerfunktion. Drucke deine Aufgaben sofort auf Bondrucker mit einer modernen Web-Oberfläche und leistungsstarker API.

## ✨ Features

- 🖨️ **Direktdruck** auf Bon-/POS-Drucker (USB, Serial, Netzwerk)
- 🌐 **Moderne Web-Oberfläche** mit responsivem Design
- 📱 **REST API** mit Bearer Token Authentifizierung
- 🔐 **Web-Authentifizierung** mit Session-Management und IP-Whitelist
- 🌍 **Mehrsprachig** (Deutsch/Englisch) - auch per API steuerbar
- ⭐ **5-Stufen Prioritätssystem** für Aufgaben
- 🤖 **KI-gestützte Motivationssprüche** (OpenAI Integration)
- 📊 **Warteschlangen-Management** mit automatischem Retry
- 🔌 **MQTT Integration** für Drucker-Energieverwaltung
- ⏱️ **Automatisches Timeout-Management**
- 🔄 **Hot-Reload** der Konfiguration (.env Änderungen)
- 📈 **Statistiken** und Queue-Monitoring

## 🚀 Schnellinstallation

### Voraussetzungen

- Linux (Debian 11+, Ubuntu 20.04+) oder macOS
- Python 3.9 oder höher
- Git

### Installation mit Skript

```bash
# 1. Projekt herunterladen
cd /opt
sudo git clone https://github.com/yourusername/paperoo.git
sudo chown -R $USER:$USER /opt/paperoo
cd paperoo

# 2. Automatische Installation
chmod +x quick_install.sh
./quick_install.sh

# 3. Konfiguration anpassen
nano .env
```

Das Installationsskript erledigt automatisch:
- ✅ Installation aller Systemabhängigkeiten
- ✅ Erstellung der Python-Umgebung
- ✅ Installation der Python-Pakete
- ✅ Generierung sicherer API-Keys
- ✅ Einrichtung der Druckerberechtigungen
- ✅ Erkennung angeschlossener USB-Drucker

## 📋 Manuelle Installation

### 1. Abhängigkeiten installieren

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip \
                         build-essential libusb-1.0-0 libusb-1.0-0-dev
```

**macOS:**
```bash
brew install python3 libusb
```

### 2. Python-Umgebung einrichten

```bash
# Virtuelle Umgebung erstellen
python3 -m venv venv

# Aktivieren
source venv/bin/activate  # Linux/macOS
# oder
venv\Scripts\activate     # Windows

# Pakete installieren
pip install -r requirements.txt
```

### 3. Konfiguration

```bash
# Vorlage kopieren
cp .env.example .env

# Bearbeiten
nano .env  # oder Editor deiner Wahl
```

### 4. Server starten

```bash
# Virtuelle Umgebung aktivieren
source venv/bin/activate

# Server starten
python app.py
```

Die Anwendung läuft dann unter: `http://localhost:5001`

## ⚙️ Konfiguration

### Wichtige Einstellungen in .env

```env
# API Sicherheit
API_KEY=your-secure-api-key-here
SECRET_KEY=your-flask-secret-key-here

# Drucker
PRINTER_TYPE=usb  # usb, serial, network
PRINTER_VENDOR_ID=0x04b8  # Für USB (mit lsusb ermitteln)
PRINTER_PRODUCT_ID=0x0e15

# Sprache
LANGUAGE=de  # de oder en

# Web-Authentifizierung (optional)
WEB_AUTH_ENABLED=true
WEB_USERNAME=admin
WEB_PASSWORD=secure-password
WEB_SESSION_TIMEOUT=1440  # Minuten

# IP-Whitelist (optional)
WEB_IP_WHITELIST_ENABLED=true
WEB_IP_WHITELIST=192.168.0.0/16,10.0.0.0/8

# OpenAI für Motivationssprüche (optional)
OPENAI_API_KEY=sk-...
MOTIVATION_ENABLED=true
MOTIVATION_MODEL=gpt-4o-mini

# MQTT (optional)
MQTT_ENABLED=false
MQTT_BROKER=localhost
```

## 🔌 API-Dokumentation

### Authentifizierung

Die API verwendet Bearer Token Authentifizierung:

```bash
Authorization: Bearer your-api-key
```

### Hauptendpunkte

#### Aufgabe drucken
`POST /api/print`

```bash
curl -X POST http://localhost:5001/api/print \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Dokumentation fertigstellen",
    "priority": 4,
    "language": "de"
  }'
```

**Parameter:**
- `text` (string, required): Aufgabentext
- `priority` (integer, 1-5): Priorität (Standard: 3)
- `language` (string): Sprache für Ausdruck ("de" oder "en")

**Antwort:**
```json
{
  "success": true,
  "message": "ToDo printed successfully",
  "data": {
    "id": 123,
    "text": "Dokumentation fertigstellen",
    "priority": 4,
    "language": "de"
  }
}
```

#### Status abrufen
`GET /api/status`

```bash
curl -X GET http://localhost:5001/api/status \
  -H "Authorization: Bearer your-api-key"
```

#### Warteschlangen-Status
`GET /api/queue/status`

Liefert Statistiken über gedruckte, wartende und fehlgeschlagene Aufgaben.

#### Fehlgeschlagene wiederholen
`POST /api/queue/retry`

Startet erneuten Druckversuch für alle fehlgeschlagenen Aufgaben.

## 🖥️ Web-Interface

### Features

- **Aufgabeneingabe** mit Zeichenzähler (max. 500)
- **Prioritätsauswahl** mit visuellen Sternen (1-5)
- **Live-Druckerstatus** und Verbindungsanzeige
- **Queue-Monitoring** inline in der Kopfzeile
- **Sprachumschaltung** (DE/EN) mit Sofort-Effekt
- **Session-basierte Authentifizierung** (optional)
- **IP-Whitelist** für zusätzliche Sicherheit

### Zugriff

Standard: `http://localhost:5001`

Mit Authentifizierung:
1. Login unter `/login`
2. Session bleibt 24 Stunden aktiv (konfigurierbar)
3. "Remember Me" Option für 30 Tage

## 🖨️ Unterstützte Drucker

- **Epson TM-Serie** (TM-T88, TM-T20, TM-T70, etc.)
- **Star Micronics** Drucker
- **Citizen** Bondrucker
- Alle **ESC/POS kompatiblen** Drucker
- Anschluss über **USB**, **Serial** oder **Netzwerk**

### Drucker-Erkennung

USB-Drucker finden:
```bash
lsusb
# Bus 001 Device 004: ID 04b8:0e15 Seiko Epson Corp.
```

Die Vendor-ID (04b8) und Product-ID (0e15) in .env eintragen.

## 🔐 Sicherheit

### Best Practices

1. **Starke API-Keys generieren:**
   ```bash
   openssl rand -hex 32
   ```

2. **HTTPS in Produktion** (nginx Reverse Proxy)

3. **Web-Authentifizierung aktivieren:**
   - Username/Passwort Schutz
   - Session-Timeout konfigurieren
   - IP-Whitelist für lokale Netze

4. **Berechtigungen:**
   - Als non-root User ausführen
   - Drucker-Gruppe korrekt setzen

5. **Firewall:**
   - Nur benötigte Ports öffnen (5001)

## 🛠️ Systemdienst einrichten

### Linux (systemd)

Service-Datei erstellen:
```bash
sudo nano /etc/systemd/system/paperoo.service
```

Inhalt:
```ini
[Unit]
Description=Paperoo Task Printer
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/opt/paperoo
Environment="PATH=/opt/paperoo/venv/bin"
ExecStart=/opt/paperoo/venv/bin/python /opt/paperoo/app.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Aktivieren und starten:
```bash
sudo systemctl daemon-reload
sudo systemctl enable paperoo
sudo systemctl start paperoo
sudo systemctl status paperoo
```

## 🐛 Fehlerbehebung

### USB-Drucker wird nicht erkannt

```bash
# Drucker-Berechtigungen prüfen
ls -l /dev/bus/usb/*/*

# Benutzer zur lp-Gruppe hinzufügen
sudo usermod -a -G lp $USER

# Udev-Regel erstellen
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="04b8", ATTR{idProduct}=="0e15", MODE="0666"' | \
sudo tee /etc/udev/rules.d/99-printer.rules

# System neu laden
sudo udevadm control --reload-rules

# Aus- und wieder einloggen!
```

### Port 5001 belegt

```bash
# Prüfen was den Port nutzt
sudo lsof -i :5001

# Alternative: Port in .env ändern
PORT=5002
```

### Python venv Fehler (Debian 12)

```bash
# python3-full installieren
sudo apt-get install python3-full python3-venv
```

## 📊 Monitoring

### Logs

- Anwendungs-Logs: `logs/` Verzeichnis
- System-Logs: `sudo journalctl -u paperoo -f`

### Queue-Status

Web-Interface zeigt in Echtzeit:
- Gesamt gedruckte Aufgaben
- Wartende Aufgaben
- Fehlgeschlagene Aufgaben
- Heute gedruckte Aufgaben

## 🤝 Beitragen

Contributions sind willkommen! Bitte erstelle einen Pull Request oder öffne ein Issue.

## 📝 Lizenz

MIT License - siehe [LICENSE](LICENSE) Datei

## 🆘 Support

Bei Problemen:
1. Logs prüfen (`logs/` Verzeichnis)
2. Issue auf GitHub erstellen
3. Debug-Modus aktivieren (`DEBUG=True` in .env)

---

**Paperoo** - Aufgaben greifbar machen! 🎯