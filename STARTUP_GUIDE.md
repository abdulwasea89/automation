# 🚀 WhatsApp Automation - Startup Guide

This guide shows you how to run the WhatsApp automation service using different methods.

## 📋 Prerequisites

1. **Python 3.11+** installed
2. **Dependencies** installed: `pip install -r requirements.txt`
3. **Environment variables** configured (see `.env` file)
4. **Service account** file present (`service-account.json`)

## 🎯 Quick Start Methods

### Method 1: Python Script (Recommended)
```bash
# Make executable and run
chmod +x run.py
python3 run.py
```

### Method 2: Bash Script
```bash
# Make executable and run
chmod +x run.sh
./run.sh
```

### Method 3: Direct Uvicorn
```bash
# Set Python path and run
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Method 4: Docker Compose
```bash
# Start with Docker
docker-compose up --build
```

## 🔧 System Service Setup

### Install as System Service
```bash
# Copy service file to systemd
sudo cp whatsapp-automation.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable whatsapp-automation
sudo systemctl start whatsapp-automation

# Check status
sudo systemctl status whatsapp-automation
```

### Service Management Commands
```bash
# Start service
sudo systemctl start whatsapp-automation

# Stop service
sudo systemctl stop whatsapp-automation

# Restart service
sudo systemctl restart whatsapp-automation

# View logs
sudo journalctl -u whatsapp-automation -f

# Disable service
sudo systemctl disable whatsapp-automation
```

## 🌐 Access Points

Once running, you can access:

- **Application**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Alternative Docs**: http://localhost:8000/redoc

## 🔍 Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Check what's using port 8000
   sudo lsof -i :8000
   
   # Kill process or use different port
   uvicorn src.main:app --host 0.0.0.0 --port 8001 --reload
   ```

2. **Import errors**
   ```bash
   # Ensure PYTHONPATH is set
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   
   # Or run from project root
   cd /path/to/automation
   python3 run.py
   ```

3. **Missing dependencies**
   ```bash
   # Install requirements
   pip install -r requirements.txt
   
   # Or recreate virtual environment
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Service account issues**
   ```bash
   # Check if service account exists
   ls -la service-account.json
   
   # Set environment variable
   export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/service-account.json"
   ```

### Debug Mode
```bash
# Run with debug logging
DEBUG=true LOG_LEVEL=DEBUG python3 run.py
```

## 📊 Monitoring

### Health Check
```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status": "ok"}
```

### Logs
```bash
# View application logs
tail -f logs/app.log

# View system service logs
sudo journalctl -u whatsapp-automation -f
```

### Performance
```bash
# Check memory usage
ps aux | grep uvicorn

# Check open connections
netstat -tulpn | grep 8000
```

## 🔄 Production Deployment

For production, use the provided deployment scripts:

```bash
# Deploy to Google Cloud Run
./deploy.sh

# Or use Docker
docker build -t whatsapp-automation .
docker run -p 8080:8080 whatsapp-automation
```

## 📞 Support

If you encounter issues:

1. Check the logs: `tail -f logs/app.log`
2. Verify environment variables: `cat .env`
3. Test health endpoint: `curl http://localhost:8000/health`
4. Check service status: `sudo systemctl status whatsapp-automation`

## 🎉 Success Indicators

When the service is running correctly, you should see:

- ✅ Uvicorn server started on port 8000
- ✅ FastAPI application loaded
- ✅ Health endpoint responding
- ✅ API documentation accessible
- ✅ No error messages in logs

---

**Happy automating! 🚀** 