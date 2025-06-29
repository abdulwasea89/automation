#!/bin/bash

# 🚀 Quick Start Script for FastAPI WhatsApp Automation
# This script helps you get started quickly with local development and deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    log_warning "This script is optimized for Linux. Some commands may need adjustment for your OS."
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install dependencies
install_dependencies() {
    log_info "Installing system dependencies..."
    
    if command_exists apt-get; then
        # Ubuntu/Debian
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv docker.io curl git
    elif command_exists yum; then
        # CentOS/RHEL
        sudo yum update -y
        sudo yum install -y python3 python3-pip docker git curl
    elif command_exists brew; then
        # macOS
        brew install python docker git curl
    else
        log_error "Unsupported package manager. Please install Python, Docker, and Git manually."
        exit 1
    fi
    
    log_success "System dependencies installed!"
}

# Setup Python environment
setup_python_env() {
    log_info "Setting up Python environment..."
    
    # Create virtual environment
    python3 -m venv .venv
    source .venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install Python dependencies
    pip install -r requirements.txt
    
    log_success "Python environment setup complete!"
}

# Setup Docker
setup_docker() {
    log_info "Setting up Docker..."
    
    # Start Docker service
    if command_exists systemctl; then
        sudo systemctl start docker
        sudo systemctl enable docker
    fi
    
    # Add user to docker group (Linux only)
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo usermod -aG docker $USER
        log_warning "You may need to log out and back in for Docker group changes to take effect."
    fi
    
    log_success "Docker setup complete!"
}

# Setup Google Cloud CLI
setup_gcloud() {
    log_info "Setting up Google Cloud CLI..."
    
    if ! command_exists gcloud; then
        # Install Google Cloud CLI
        curl https://sdk.cloud.google.com | bash
        exec -l $SHELL
        log_warning "Please restart your terminal or run 'source ~/.bashrc' to use gcloud."
    fi
    
    log_success "Google Cloud CLI setup complete!"
}

# Create environment file
create_env_file() {
    log_info "Creating environment file..."
    
    if [ ! -f .env ]; then
        cat > .env << EOF
# Google Cloud Configuration
PROJECT_ID=ai-chatbot-463111
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json

# OpenAI Configuration
OPENAI_API_KEY=YOUR_OPENAI_API_KEY_HERE

# Shopify Configuration
SHOPIFY_API_KEY=YOUR_SHOPIFY_API_KEY_HERE
SHOPIFY_API_PASSWORD=YOUR_SHOPIFY_API_PASSWORD_HERE
SHOPIFY_STORE_NAME=835e8e

# Zoko Configuration
ZOKO_API_KEY=YOUR_ZOKO_API_KEY_HERE
ZOKO_API_URL=https://chat.zoko.io/v2/message

# API Configuration
API_KEY=YOUR_API_KEY_HERE

# Rate Limiting
RATE_LIMIT=30
RATE_PERIOD=60

# Caching
CACHE_TTL=3600

# Application Configuration
DEBUG=true
LOG_LEVEL=INFO
EOF
        log_success "Created .env file with all environment variables."
    else
        log_info ".env file already exists."
    fi
}

# Test local setup
test_local_setup() {
    log_info "Testing local setup..."
    
    # Test Python
    python3 --version
    
    # Test Docker
    docker --version
    
    # Test if app can start
    if [ -f app.py ]; then
        log_info "Testing FastAPI application..."
        timeout 10s python3 -c "
import sys
sys.path.append('.')
try:
    from app import app
    print('✅ FastAPI app imports successfully')
except Exception as e:
    print(f'❌ Error importing app: {e}')
    sys.exit(1)
" || log_warning "App import test failed (this is normal if dependencies are missing)"
    fi
    
    log_success "Local setup test complete!"
}

# Show next steps
show_next_steps() {
    echo ""
    log_success "🎉 Quick start setup complete!"
    echo ""
    log_info "Next steps:"
    echo "1. Update .env file with your actual API keys and project ID"
    echo "2. Set up Google Cloud project and service account"
    echo "3. Run local development:"
    echo "   docker-compose up --build"
    echo "4. Deploy to production:"
    echo "   ./deploy.sh"
    echo ""
    log_info "Useful commands:"
    echo "  Local development: docker-compose up --build"
    echo "  Run tests: python -m pytest tests/"
    echo "  Deploy: ./deploy.sh"
    echo "  View logs: docker-compose logs -f"
    echo ""
    log_info "Documentation:"
    echo "  - Deployment Guide: DEPLOYMENT_GUIDE.md"
    echo "  - API Documentation: http://localhost:8000/docs (when running)"
    echo "  - Health Check: http://localhost:8000/health (when running)"
}

# Main function
main() {
    echo "🚀 FastAPI WhatsApp Automation - Quick Start"
    echo "============================================="
    echo ""
    
    # Check if we're in the right directory
    if [ ! -f "app.py" ] && [ ! -f "requirements.txt" ]; then
        log_error "Please run this script from the project root directory."
        exit 1
    fi
    
    # Install dependencies
    install_dependencies
    
    # Setup Python environment
    setup_python_env
    
    # Setup Docker
    setup_docker
    
    # Setup Google Cloud CLI
    setup_gcloud
    
    # Create environment file
    create_env_file
    
    # Test setup
    test_local_setup
    
    # Show next steps
    show_next_steps
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  --skip-deps         Skip system dependency installation"
    echo "  --skip-python       Skip Python environment setup"
    echo "  --skip-docker       Skip Docker setup"
    echo "  --skip-gcloud       Skip Google Cloud CLI setup"
    echo ""
    echo "This script will:"
    echo "  1. Install system dependencies (Python, Docker, Git)"
    echo "  2. Set up Python virtual environment"
    echo "  3. Install Python dependencies"
    echo "  4. Configure Docker"
    echo "  5. Install Google Cloud CLI"
    echo "  6. Create environment file template"
    echo "  7. Test the setup"
}

# Parse command line arguments
SKIP_DEPS=false
SKIP_PYTHON=false
SKIP_DOCKER=false
SKIP_GCLOUD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --skip-python)
            SKIP_PYTHON=true
            shift
            ;;
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --skip-gcloud)
            SKIP_GCLOUD=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run main function
main 