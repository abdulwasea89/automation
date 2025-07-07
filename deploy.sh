# Create systemd service file
echo -e "${BLUE}🔧 Creating systemd service...${NC}"
sudo tee $SERVICE_FILE > /dev/null << EOF
[Unit]
Description=LEVA WhatsApp Assistant
After=network.target

[Service]
Type=exec
User=$USER
Group=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/gunicorn -c gunicorn_config.py src.main:app
Restart=always
RestartSec=10
TimeoutStartSec=60
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
print_status "Systemd service file created"

# Install dependencies
echo -e "${BLUE}📦 Installing dependencies...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    # Install Gunicorn for production
    pip install gunicorn
    print_status "Dependencies installed"
else
    print_error "requirements.txt not found"
    exit 1
fi 