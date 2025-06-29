#!/bin/bash

# 🚀 FastAPI WhatsApp Automation - Run Service Script
# This script starts the FastAPI application for local development

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Configuration
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-"8000"}
WORKERS=${WORKERS:-"1"}
RELOAD=${RELOAD:-"true"}
LOG_LEVEL=${LOG_LEVEL:-"info"}

# Check if Python is installed
check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed. Please install Python 3.11+ first."
        exit 1
    fi
    
    python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
    required_version="3.11"
    
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
        log_warning "Python version $python_version detected. Python 3.11+ is recommended."
    fi
    
    log_success "Python check passed!"
}

# Check if virtual environment exists
check_venv() {
    if [ ! -d ".venv" ]; then
        log_warning "Virtual environment not found. Creating one..."
        python3 -m venv .venv
        log_success "Virtual environment created!"
    fi
    
    # Activate virtual environment
    source .venv/bin/activate
    log_success "Virtual environment activated!"
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."
    
    if [ -f "requirements.txt" ]; then
        pip install --upgrade pip
        pip install -r requirements.txt
        log_success "Dependencies installed!"
    else
        log_error "requirements.txt not found!"
        exit 1
    fi
}

# Check environment variables
check_env() {
    log_info "Checking environment variables..."
    
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        log_warning ".env file not found. Creating from example..."
        if [ -f "env.example" ]; then
            cp env.example .env
            log_warning "Please update .env file with your actual API keys and configuration."
        else
            log_error "No .env file or env.example found. Please create .env file manually."
            exit 1
        fi
    fi
    
    # Load environment variables
    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
        log_success "Environment variables loaded!"
    fi
}

# Check if service account file exists
check_service_account() {
    if [ ! -f "service-account.json" ]; then
        log_warning "service-account.json not found. Application will run without Google Cloud features."
        log_info "To enable Google Cloud features, please add your service-account.json file."
    else
        log_success "Service account file found!"
    fi
}

# Start the application
start_app() {
    log_info "Starting FastAPI application..."
    log_info "Host: $HOST"
    log_info "Port: $PORT"
    log_info "Workers: $WORKERS"
    log_info "Reload: $RELOAD"
    log_info "Log Level: $LOG_LEVEL"
    
    # Set Python path
    export PYTHONPATH="${PYTHONPATH}:$(pwd)"
    
    if [ "$RELOAD" = "true" ]; then
        # Development mode with auto-reload
        log_info "Starting in development mode with auto-reload..."
        uvicorn src.main:app \
            --host "$HOST" \
            --port "$PORT" \
            --reload \
            --log-level "$LOG_LEVEL" \
            --reload-dir src \
            --reload-dir templates.json \
            --reload-dir zoko_templates.json
    else
        # Production mode with gunicorn
        log_info "Starting in production mode with gunicorn..."
        gunicorn src.main:app \
            --bind "$HOST:$PORT" \
            --workers "$WORKERS" \
            --worker-class uvicorn.workers.UvicornWorker \
            --timeout 120 \
            --keep-alive 5 \
            --log-level "$LOG_LEVEL"
    fi
}

# Show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -p, --port PORT     Port to run on (default: 8000)"
    echo "  -H, --host HOST     Host to bind to (default: 0.0.0.0)"
    echo "  -w, --workers N     Number of workers (default: 1)"
    echo "  -r, --reload        Enable auto-reload (default: true)"
    echo "  -l, --log-level     Log level (default: info)"
    echo "  --prod              Run in production mode (no reload)"
    echo ""
    echo "Environment Variables:"
    echo "  HOST                Host to bind to"
    echo "  PORT                Port to run on"
    echo "  WORKERS             Number of workers"
    echo "  RELOAD              Enable auto-reload (true/false)"
    echo "  LOG_LEVEL           Log level"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run with defaults"
    echo "  $0 -p 9000                           # Run on port 9000"
    echo "  $0 --prod                            # Run in production mode"
    echo "  $0 -H 127.0.0.1 -p 8000              # Run on localhost:8000"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -H|--host)
            HOST="$2"
            shift 2
            ;;
        -w|--workers)
            WORKERS="$2"
            shift 2
            ;;
        -r|--reload)
            RELOAD="true"
            shift
            ;;
        -l|--log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --prod)
            RELOAD="false"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main function
main() {
    log_info "🚀 Starting FastAPI WhatsApp Automation Service"
    log_info "Project: $(pwd)"
    
    # Run all checks
    check_python
    check_venv
    install_dependencies
    check_env
    check_service_account
    
    log_success "All checks passed! Starting application..."
    echo ""
    log_info "📱 Application will be available at:"
    log_info "   Local: http://localhost:$PORT"
    log_info "   Network: http://$HOST:$PORT"
    log_info "   API Docs: http://localhost:$PORT/docs"
    log_info "   Health Check: http://localhost:$PORT/health"
    echo ""
    log_info "Press Ctrl+C to stop the application"
    echo ""
    
    # Start the application
    start_app
}

# Run main function
main 