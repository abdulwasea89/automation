#!/bin/bash

# 🚀 LEVA WhatsApp Assistant - Development Startup Script
# This script starts the application in development mode with Uvicorn

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🏠 LEVA WhatsApp Assistant - Development Mode${NC}"
echo "=================================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}🔧 Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✅ Virtual environment activated${NC}"

# Install dependencies if needed
if [ ! -f "venv/lib/python*/site-packages/fastapi" ]; then
    echo -e "${BLUE}📦 Installing dependencies...${NC}"
    pip install -r requirements.txt
    echo -e "${GREEN}✅ Dependencies installed${NC}"
fi

# Check environment file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating template...${NC}"
    cat > .env << EOF
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Zoko Configuration
ZOKO_API_KEY=your_zoko_api_key_here
ZOKO_BASE_URL=https://api.zoko.com/v1

# Firebase Configuration
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
FIREBASE_PROJECT_ID=your_project_id_here

# Application Configuration
LOG_LEVEL=INFO
PORT=8000
EOF
    echo -e "${YELLOW}⚠️  Please edit .env file with your actual credentials${NC}"
    echo -e "${YELLOW}⚠️  Then run this script again${NC}"
    exit 1
fi

# Check Firebase service account
if [ ! -f "service-account.json" ]; then
    echo -e "${YELLOW}⚠️  service-account.json not found${NC}"
    echo -e "${YELLOW}⚠️  Please download your Firebase service account JSON file${NC}"
    echo -e "${YELLOW}⚠️  and place it in the root directory as 'service-account.json'${NC}"
    exit 1
fi

# Test the application
echo -e "${BLUE}🧪 Testing application...${NC}"
python test_extraction.py
echo -e "${GREEN}✅ Extraction logic test passed${NC}"

# Start development server
echo -e "${BLUE}🚀 Starting development server...${NC}"
echo -e "${GREEN}✅ Server will be available at: http://localhost:8000${NC}"
echo -e "${GREEN}✅ Health check: http://localhost:8000/health${NC}"
echo -e "${GREEN}✅ API docs: http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}📋 Development mode features:${NC}"
echo "- Auto-reload on code changes"
echo "- Detailed error messages"
echo "- Debug logging enabled"
echo "- Hot reload for development"
echo ""
echo -e "${BLUE}Press Ctrl+C to stop the server${NC}"
echo "=================================================="

# Start Uvicorn in development mode
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 --log-level info 