# Paperoo 🎯

An intelligent task manager with receipt printer functionality. Print your tasks instantly on receipt printers with a modern web interface and powerful API.

## ✨ Features

- 🖨️ **Direct printing** on receipt/POS printers (USB, Serial, Network)
- 🌐 **Modern web interface** with responsive design
- 📱 **REST API** with Bearer Token authentication
- 🔐 **Web authentication** with session management and IP whitelist
- 🌍 **Multilingual** (German/English) - controllable via API
- ⭐ **5-level priority system** for tasks
- 🤖 **AI-powered motivational quotes** (OpenAI integration)
- 📊 **Queue management** with automatic retry
- 🔌 **MQTT integration** for printer power management
- ⏱️ **Automatic timeout management**
- 🔄 **Hot-reload** of configuration (.env changes)
- 📈 **Statistics** and queue monitoring

## 🚀 Quick Installation

### Prerequisites

- Linux (Debian 11+, Ubuntu 20.04+) or macOS
- Python 3.9 or higher
- Git

### Installation with Script

```bash
# 1. Download project
cd /opt
sudo git clone https://github.com/yourusername/paperoo.git
sudo chown -R $USER:$USER /opt/paperoo
cd paperoo

# 2. Automatic installation
chmod +x quick_install.sh
./quick_install.sh

# 3. Adjust configuration
nano .env
```

The installation script automatically handles:
- ✅ Installation of all system dependencies
- ✅ Creation of Python environment
- ✅ Installation of Python packages
- ✅ Generation of secure API keys
- ✅ Setup of printer permissions
- ✅ Detection of connected USB printers

## 📋 Manual Installation

### 1. Install Dependencies

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

### 2. Setup Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install packages
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy template
cp .env.example .env

# Edit
nano .env  # or your preferred editor
```

### 4. Start Server

```bash
# Activate virtual environment
source venv/bin/activate

# Start server
python app.py
```

The application will run at: `http://localhost:5001`

## ⚙️ Configuration

### Important Settings in .env

```env
# API Security
API_KEY=your-secure-api-key-here
SECRET_KEY=your-flask-secret-key-here

# Printer
PRINTER_TYPE=usb  # usb, serial, network
PRINTER_VENDOR_ID=0x04b8  # For USB (determine with lsusb)
PRINTER_PRODUCT_ID=0x0e15

# Language
LANGUAGE=en  # de or en

# Web Authentication (optional)
WEB_AUTH_ENABLED=true
WEB_USERNAME=admin
WEB_PASSWORD=secure-password
WEB_SESSION_TIMEOUT=1440  # minutes

# IP Whitelist (optional)
WEB_IP_WHITELIST_ENABLED=true
WEB_IP_WHITELIST=192.168.0.0/16,10.0.0.0/8

# OpenAI for motivational quotes (optional)
OPENAI_API_KEY=sk-...
MOTIVATION_ENABLED=true
MOTIVATION_MODEL=gpt-4o-mini

# MQTT (optional)
MQTT_ENABLED=false
MQTT_BROKER=localhost
```

## 🔌 API Documentation

### Authentication

The API uses Bearer Token authentication:

```bash
Authorization: Bearer your-api-key
```

### Main Endpoints

#### Print Task
`POST /api/print`

```bash
curl -X POST http://localhost:5001/api/print \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Complete documentation",
    "priority": 4,
    "language": "en"
  }'
```

**Parameters:**
- `text` (string, required): Task text
- `priority` (integer, 1-5): Priority (default: 3)
- `language` (string): Language for printout ("de" or "en")

**Response:**
```json
{
  "success": true,
  "message": "ToDo printed successfully",
  "data": {
    "id": 123,
    "text": "Complete documentation",
    "priority": 4,
    "language": "en"
  }
}
```

#### Get Status
`GET /api/status`

```bash
curl -X GET http://localhost:5001/api/status \
  -H "Authorization: Bearer your-api-key"
```

#### Queue Status
`GET /api/queue/status`

Returns statistics about printed, pending, and failed tasks.

#### Retry Failed
`POST /api/queue/retry`

Starts retry attempt for all failed tasks.

## 🖥️ Web Interface

### Features

- **Task input** with character counter (max. 500)
- **Priority selection** with visual stars (1-5)
- **Live printer status** and connection display
- **Queue monitoring** inline in header
- **Language switching** (DE/EN) with instant effect
- **Session-based authentication** (optional)
- **IP whitelist** for additional security

### Access

Default: `http://localhost:5001`

With authentication:
1. Login at `/login`
2. Session stays active for 24 hours (configurable)
3. "Remember Me" option for 30 days

## 🖨️ Supported Printers

- **Epson TM-Series** (TM-T88, TM-T20, TM-T70, etc.)
- **Star Micronics** printers
- **Citizen** receipt printers
- All **ESC/POS compatible** printers
- Connection via **USB**, **Serial** or **Network**

### Printer Detection

Find USB printer:
```bash
lsusb
# Bus 001 Device 004: ID 04b8:0e15 Seiko Epson Corp.
```

Enter the Vendor-ID (04b8) and Product-ID (0e15) in .env.

## 🔐 Security

### Best Practices

1. **Generate strong API keys:**
   ```bash
   openssl rand -hex 32
   ```

2. **HTTPS in production** (nginx reverse proxy)

3. **Enable web authentication:**
   - Username/password protection
   - Configure session timeout
   - IP whitelist for local networks

4. **Permissions:**
   - Run as non-root user
   - Set printer group correctly

5. **Firewall:**
   - Only open required ports (5001)

## 🛠️ Setup System Service

### Linux (systemd)

Create service file:
```bash
sudo nano /etc/systemd/system/paperoo.service
```

Content:
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

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable paperoo
sudo systemctl start paperoo
sudo systemctl status paperoo
```

## 🐛 Troubleshooting

### USB Printer Not Recognized

```bash
# Check printer permissions
ls -l /dev/bus/usb/*/*

# Add user to lp group
sudo usermod -a -G lp $USER

# Create udev rule
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="04b8", ATTR{idProduct}=="0e15", MODE="0666"' | \
sudo tee /etc/udev/rules.d/99-printer.rules

# Reload system
sudo udevadm control --reload-rules

# Log out and back in!
```

### Port 5001 Already in Use

```bash
# Check what's using the port
sudo lsof -i :5001

# Alternative: Change port in .env
PORT=5002
```

### Python venv Error (Debian 12)

```bash
# Install python3-full
sudo apt-get install python3-full python3-venv
```

## 📊 Monitoring

### Logs

- Application logs: `logs/` directory
- System logs: `sudo journalctl -u paperoo -f`

### Queue Status

Web interface shows in real-time:
- Total printed tasks
- Pending tasks
- Failed tasks
- Today's printed tasks

## 🤝 Contributing

Contributions are welcome! Please create a pull request or open an issue.

## 📝 License

MIT License - see [LICENSE](LICENSE) file

## 🆘 Support

For issues:
1. Check logs (`logs/` directory)
2. Create issue on GitHub
3. Enable debug mode (`DEBUG=True` in .env)

---

**Paperoo** - Making tasks tangible! 🎯