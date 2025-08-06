#!/bin/bash

# ToDo Printer Server - Universal Installation Script
# Repository: https://github.com/Digitmedia-de/ToDo-Printer-Server
# Supports: x86_64, ARM (Raspberry Pi), Debian/Ubuntu

# Don't exit on error immediately
set +e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}    ToDo Printer Server - Universal Installer  ${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Detect system architecture
ARCH=$(uname -m)
OS=$(uname -s)
echo "System Detection:"
echo "  OS: $OS"
echo "  Architecture: $ARCH"

if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "  Distribution: $PRETTY_NAME"
fi
echo ""

# Check if running on Debian/Ubuntu
if ! command -v apt-get &> /dev/null; then
    echo -e "${RED}Error: This script requires apt-get (Debian/Ubuntu systems).${NC}"
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Install system dependencies
echo -e "${YELLOW}Step 1: Installing system dependencies...${NC}"

# Update package list
sudo apt-get update || true

# Install Python packages based on what's available
echo "Installing Python and dependencies..."

# Try to install Python 3 with different package names
if ! command_exists python3; then
    sudo apt-get install -y python3 || sudo apt-get install -y python3.11 || sudo apt-get install -y python3.10
fi

# Install venv - try different approaches
sudo apt-get install -y python3-venv 2>/dev/null || \
sudo apt-get install -y python3.11-venv 2>/dev/null || \
sudo apt-get install -y python3-full 2>/dev/null || true

# Install other dependencies
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    build-essential \
    libusb-1.0-0 \
    libusb-1.0-0-dev \
    libudev-dev \
    git \
    curl \
    wget \
    openssl 2>/dev/null || true

echo -e "${GREEN}✓ System dependencies installed${NC}"

# Step 2: Check if we're in the right directory
if [[ ! -f "app.py" ]]; then
    echo -e "${RED}Error: app.py not found!${NC}"
    echo -e "${RED}Please run this script from the ToDo-Printer-Server directory.${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 2: Using current directory...${NC}"
CURRENT_DIR=$(pwd)

# Step 3: Setup Python virtual environment
echo -e "${YELLOW}Step 3: Setting up Python virtual environment...${NC}"

# Find working Python command
PYTHON_CMD=""
for cmd in python3 python3.11 python3.10 python3.9 python; do
    if command_exists $cmd; then
        if $cmd --version &> /dev/null; then
            PYTHON_CMD=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}Error: No working Python installation found!${NC}"
    echo "Attempting to fix Python installation..."
    
    # Try to reinstall Python
    sudo apt-get install --reinstall -y python3 python3-minimal
    
    # Check again
    if command_exists python3 && python3 --version &> /dev/null; then
        PYTHON_CMD="python3"
    else
        echo -e "${RED}Failed to install Python. Please install manually.${NC}"
        exit 1
    fi
fi

echo "Using Python: $($PYTHON_CMD --version 2>&1)"

# Remove old virtual environment
if [[ -d "venv" ]]; then
    echo "Removing old virtual environment..."
    rm -rf venv
fi

# Try to create virtual environment
echo "Creating virtual environment..."
if ! $PYTHON_CMD -m venv venv 2>/dev/null; then
    echo -e "${YELLOW}venv module not available, trying alternative methods...${NC}"
    
    # Try installing venv module
    sudo apt-get install -y ${PYTHON_CMD}-venv 2>/dev/null || true
    
    # Try again
    if ! $PYTHON_CMD -m venv venv 2>/dev/null; then
        echo -e "${YELLOW}Creating virtual environment with --without-pip...${NC}"
        $PYTHON_CMD -m venv venv --without-pip || {
            echo -e "${RED}Cannot create virtual environment. Installing packages globally...${NC}"
            USE_VENV=false
        }
    fi
else
    USE_VENV=true
fi

# Activate virtual environment if created
if [ "$USE_VENV" != "false" ] && [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || . venv/bin/activate 2>/dev/null || {
        echo -e "${YELLOW}Could not activate venv, continuing anyway...${NC}"
    }
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}⚠ Installing packages globally (no venv)${NC}"
fi

# Step 4: Install Python packages
echo -e "${YELLOW}Step 4: Installing Python packages...${NC}"

# Determine pip command
if [ "$USE_VENV" != "false" ] && [ -d "venv" ]; then
    PIP_CMD="pip"
else
    # Find pip command
    if command_exists pip3; then
        PIP_CMD="pip3"
    elif command_exists pip; then
        PIP_CMD="pip"
    else
        echo "Installing pip..."
        $PYTHON_CMD -m ensurepip 2>/dev/null || \
        sudo apt-get install -y python3-pip || \
        curl https://bootstrap.pypa.io/get-pip.py | $PYTHON_CMD
        PIP_CMD="pip3"
    fi
fi

# Upgrade pip
$PIP_CMD install --upgrade pip 2>/dev/null || true

# Install packages
echo "Installing Python packages..."
if [ "$USE_VENV" != "false" ]; then
    $PIP_CMD install wheel 2>/dev/null || true
    $PIP_CMD install -r requirements.txt || {
        echo -e "${YELLOW}Some packages failed, installing one by one...${NC}"
        for package in Flask flask-cors python-escpos pyserial paho-mqtt python-dotenv Werkzeug Pillow; do
            $PIP_CMD install $package 2>/dev/null || true
        done
    }
    $PIP_CMD install pyusb 2>/dev/null || true
else
    # Global installation with --break-system-packages flag for newer systems
    $PIP_CMD install --break-system-packages wheel 2>/dev/null || $PIP_CMD install wheel 2>/dev/null || true
    $PIP_CMD install --break-system-packages -r requirements.txt 2>/dev/null || $PIP_CMD install -r requirements.txt || {
        echo -e "${YELLOW}Installing packages individually...${NC}"
        for package in Flask flask-cors python-escpos pyserial paho-mqtt python-dotenv Werkzeug Pillow; do
            $PIP_CMD install --break-system-packages $package 2>/dev/null || $PIP_CMD install $package 2>/dev/null || true
        done
    }
    $PIP_CMD install --break-system-packages pyusb 2>/dev/null || $PIP_CMD install pyusb 2>/dev/null || true
fi

echo -e "${GREEN}✓ Python packages installed${NC}"

# Step 5: Setup configuration
echo -e "${YELLOW}Step 5: Setting up configuration...${NC}"

if [[ ! -f ".env" ]]; then
    cp .env.example .env
    echo -e "${YELLOW}Created .env file from template${NC}"
    
    # Generate secure random keys
    echo "Generating secure keys..."
    
    # Generate secure keys - try multiple methods
    if [ -n "$PYTHON_CMD" ] && $PYTHON_CMD -c "import secrets" 2>/dev/null; then
        # Method 1: Python secrets (most secure)
        API_KEY=$($PYTHON_CMD -c 'import secrets; print(secrets.token_urlsafe(32))')
        SECRET_KEY=$($PYTHON_CMD -c 'import secrets; print(secrets.token_urlsafe(32))')
    elif command_exists openssl; then
        # Method 2: OpenSSL
        API_KEY=$(openssl rand -base64 32 | tr -d "=+/\n" | cut -c1-43)
        SECRET_KEY=$(openssl rand -base64 32 | tr -d "=+/\n" | cut -c1-43)
    else
        # Method 3: /dev/urandom
        API_KEY=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)
        SECRET_KEY=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)
    fi
    
    # Update .env with generated keys
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS sed syntax
        sed -i '' "s/your-secure-api-key-here/$API_KEY/g" .env
        sed -i '' "s/your-flask-secret-key-here/$SECRET_KEY/g" .env
    else
        # Linux sed syntax
        sed -i "s/your-secure-api-key-here/$API_KEY/g" .env
        sed -i "s/your-flask-secret-key-here/$SECRET_KEY/g" .env
    fi
    
    echo -e "${GREEN}✓ Generated secure API and secret keys${NC}"
    
    # Save keys to a secure file for reference
    echo "==========================================" > .keys_backup
    echo "IMPORTANT: Save these keys securely!" >> .keys_backup
    echo "Generated on: $(date)" >> .keys_backup
    echo "==========================================" >> .keys_backup
    echo "API_KEY=$API_KEY" >> .keys_backup
    echo "SECRET_KEY=$SECRET_KEY" >> .keys_backup
    echo "==========================================" >> .keys_backup
    chmod 600 .keys_backup
    
    echo -e "${YELLOW}Keys saved to .keys_backup (keep this file secure!)${NC}"
else
    echo -e "${YELLOW}.env file already exists${NC}"
    
    # Check if keys are still default
    if grep -q "your-secure-api-key-here" .env || grep -q "your-flask-secret-key-here" .env; then
        echo -e "${YELLOW}Warning: Default keys detected. Generating new secure keys...${NC}"
        
        # Generate new keys
        if [ -n "$PYTHON_CMD" ] && $PYTHON_CMD -c "import secrets" 2>/dev/null; then
            NEW_API_KEY=$($PYTHON_CMD -c 'import secrets; print(secrets.token_urlsafe(32))')
            NEW_SECRET_KEY=$($PYTHON_CMD -c 'import secrets; print(secrets.token_urlsafe(32))')
        else
            NEW_API_KEY=$(openssl rand -base64 32 | tr -d "=+/\n" | cut -c1-43)
            NEW_SECRET_KEY=$(openssl rand -base64 32 | tr -d "=+/\n" | cut -c1-43)
        fi
        
        # Update only default keys
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s/your-secure-api-key-here/$NEW_API_KEY/g" .env
            sed -i '' "s/your-flask-secret-key-here/$NEW_SECRET_KEY/g" .env
        else
            sed -i "s/your-secure-api-key-here/$NEW_API_KEY/g" .env
            sed -i "s/your-flask-secret-key-here/$NEW_SECRET_KEY/g" .env
        fi
        
        echo -e "${GREEN}✓ Updated default keys with secure ones${NC}"
    else
        echo -e "${GREEN}✓ Keeping existing configuration${NC}"
    fi
fi

# Step 6: Add user to printer group
echo -e "${YELLOW}Step 6: Setting up printer permissions...${NC}"
sudo usermod -a -G lp $USER
echo -e "${GREEN}✓ User added to 'lp' group${NC}"

# Step 7: Create necessary directories
echo -e "${YELLOW}Step 7: Creating directories...${NC}"
mkdir -p logs docs docs_com
echo -e "${GREEN}✓ Directories created${NC}"

# Step 8: Show printer detection
echo -e "${YELLOW}Step 8: Detecting USB printers...${NC}"
echo "USB devices found:"
lsusb | grep -i "print\|epson\|star\|bixolon\|citizen" || echo "No known printers detected via USB"

# Step 9: Setup systemd service for autostart
echo ""
echo -e "${YELLOW}Step 9: Setting up autostart service...${NC}"

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/todo-printer.service"
SERVICE_CONTENT="[Unit]
Description=ToDo Printer Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
Environment=\"PATH=$CURRENT_DIR/venv/bin\"
ExecStart=$CURRENT_DIR/venv/bin/python $CURRENT_DIR/app.py
Restart=on-failure
RestartSec=10
StandardOutput=append:$CURRENT_DIR/logs/service.log
StandardError=append:$CURRENT_DIR/logs/service_error.log

[Install]
WantedBy=multi-user.target"

echo -e "${YELLOW}Do you want to install as system service for autostart? (y/n)${NC}"
read -r install_service

if [[ "$install_service" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    # Write service file
    echo "$SERVICE_CONTENT" | sudo tee $SERVICE_FILE > /dev/null
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable service for autostart
    sudo systemctl enable todo-printer.service
    
    echo -e "${GREEN}✓ Service installed and enabled for autostart${NC}"
    echo ""
    echo "Service commands:"
    echo -e "  Start:   ${BLUE}sudo systemctl start todo-printer${NC}"
    echo -e "  Stop:    ${BLUE}sudo systemctl stop todo-printer${NC}"
    echo -e "  Status:  ${BLUE}sudo systemctl status todo-printer${NC}"
    echo -e "  Logs:    ${BLUE}sudo journalctl -u todo-printer -f${NC}"
    echo -e "  Disable: ${BLUE}sudo systemctl disable todo-printer${NC}"
    
    echo ""
    echo -e "${YELLOW}Do you want to start the service now? (y/n)${NC}"
    read -r start_now
    
    if [[ "$start_now" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        sudo systemctl start todo-printer
        sleep 2
        
        # Check if service is running
        if systemctl is-active --quiet todo-printer; then
            echo -e "${GREEN}✓ Service started successfully!${NC}"
            echo -e "Server is running at: ${BLUE}http://localhost:5001${NC}"
        else
            echo -e "${RED}Service failed to start. Check logs with:${NC}"
            echo -e "${BLUE}sudo journalctl -u todo-printer -n 50${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Skipping service installation${NC}"
    echo "You can install it later by running:"
    echo -e "${BLUE}sudo bash -c 'cat > /etc/systemd/system/todo-printer.service << EOF"
    echo "$SERVICE_CONTENT"
    echo "EOF'"
    echo "sudo systemctl daemon-reload"
    echo "sudo systemctl enable todo-printer"
    echo "sudo systemctl start todo-printer${NC}"
fi

# Final instructions
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}    Installation completed successfully!        ${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "${BLUE}Your API Key:${NC} $(grep API_KEY .env | cut -d'=' -f2)"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Configure your printer in .env file:"
echo -e "   ${BLUE}nano .env${NC}"
echo ""
echo "2. For USB printers, find your printer with:"
echo -e "   ${BLUE}lsusb${NC}"
echo "   Then update PRINTER_VENDOR_ID and PRINTER_PRODUCT_ID in .env"
echo ""
echo "3. IMPORTANT: Logout and login again for printer group changes!"
echo -e "   ${BLUE}logout${NC}"
echo ""
echo "4. After login, start the server:"
echo -e "   ${BLUE}cd $CURRENT_DIR${NC}"
echo -e "   ${BLUE}source venv/bin/activate${NC}"
echo -e "   ${BLUE}python app.py${NC}"
echo ""
echo "5. Access the web interface at:"
echo -e "   ${BLUE}http://localhost:5001${NC}"
echo ""

# Check if service is running
if systemctl is-active --quiet todo-printer 2>/dev/null; then
    echo -e "${GREEN}✓ ToDo Printer Server is already running as a service${NC}"
    echo -e "Access the web interface at: ${BLUE}http://localhost:5001${NC}"
else
    # Ask if user wants to start the server now (if not installed as service)
    echo -e "${YELLOW}Do you want to start the server now? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo -e "${GREEN}Starting ToDo Printer Server...${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        python app.py
    fi
fi