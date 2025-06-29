#!/bin/bash

# 🚀 FastAPI WhatsApp Automation Deployment Script
# This script automates the deployment process to Google Cloud Run

set -e  # Exit on any error

# Configuration
PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-"ai-chatbot-463111"}
REGION=${REGION:-"us-central1"}
SERVICE_NAME=${SERVICE_NAME:-"whatsapp-automation"}
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"
TAG=${TAG:-$(date +%Y%m%d-%H%M%S)}

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_error "Not authenticated with gcloud. Please run 'gcloud auth login' first."
    exit 1
fi

    # Check if project is set
    if [ "$PROJECT_ID" = "your-project-id" ]; then
        log_error "Please set GOOGLE_CLOUD_PROJECT environment variable or update PROJECT_ID in this script."
        exit 1
    fi
    
    log_success "Prerequisites check passed!"
}

# Enable required APIs
enable_apis() {
    log_info "Enabling required Google Cloud APIs..."
    
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
        containerregistry.googleapis.com \
    firestore.googleapis.com \
        storage.googleapis.com \
        --project="$PROJECT_ID"
    
    log_success "APIs enabled successfully!"
}

# Build and push Docker image
build_and_push() {
    log_info "Building Docker image..."
    
    # Build the image
    docker build -t "$IMAGE_NAME:$TAG" .
    docker build -t "$IMAGE_NAME:latest" .
    
    log_success "Docker image built successfully!"
    
    log_info "Pushing Docker image to Container Registry..."
    
    # Push the image
    docker push "$IMAGE_NAME:$TAG"
    docker push "$IMAGE_NAME:latest"
    
    log_success "Docker image pushed successfully!"
}

# Deploy to Cloud Run
deploy_to_cloud_run() {
    log_info "Deploying to Cloud Run..."
    
    # Deploy the service
    gcloud run deploy "$SERVICE_NAME" \
        --image "$IMAGE_NAME:$TAG" \
        --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --timeout 300 \
        --set-env-vars GOOGLE_APPLICATION_CREDENTIALS=/app/service-account.json,PROJECT_ID=ai-chatbot-463111,OPENAI_API_KEY=YOUR_OPENAI_API_KEY_HERE,SHOPIFY_API_KEY=YOUR_SHOPIFY_API_KEY_HERE,SHOPIFY_API_PASSWORD=YOUR_SHOPIFY_API_PASSWORD_HERE,SHOPIFY_STORE_NAME=835e8e,ZOKO_API_KEY=YOUR_ZOKO_API_KEY_HERE,ZOKO_API_URL=https://chat.zoko.io/v2/message,API_KEY=YOUR_API_KEY_HERE,RATE_LIMIT=30,RATE_PERIOD=60,CACHE_TTL=3600,DEBUG=false,LOG_LEVEL=INFO \
        --project "$PROJECT_ID"
    
    log_success "Deployment completed successfully!"
}

# Get service URL
get_service_url() {
    log_info "Getting service URL..."
    
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region="$REGION" \
        --format="value(status.url)" \
        --project="$PROJECT_ID")
    
    log_success "Service URL: $SERVICE_URL"
    log_info "API Documentation: $SERVICE_URL/docs"
    log_info "Health Check: $SERVICE_URL/health"
}

# Run tests
run_tests() {
    log_info "Running tests..."
    
    if [ -d "tests" ]; then
        python -m pytest tests/ -v
        log_success "Tests completed!"
    else
        log_warning "No tests directory found. Skipping tests."
    fi
}

# Clean up old images
cleanup_old_images() {
    log_info "Cleaning up old Docker images..."
    
    # Keep only the last 5 images
    docker images "$IMAGE_NAME" --format "table {{.Repository}}:{{.Tag}}\t{{.CreatedAt}}" | \
        tail -n +2 | \
        sort -k2 -r | \
        tail -n +6 | \
        awk '{print $1}' | \
        xargs -r docker rmi || true
    
    log_success "Cleanup completed!"
}

# Main deployment function
main() {
    log_info "Starting deployment process..."
    log_info "Project ID: $PROJECT_ID"
    log_info "Region: $REGION"
    log_info "Service Name: $SERVICE_NAME"
    log_info "Image Tag: $TAG"
    
    # Run all steps
    check_prerequisites
    enable_apis
    run_tests
    build_and_push
    deploy_to_cloud_run
    get_service_url
    cleanup_old_images
    
    log_success "🎉 Deployment completed successfully!"
    log_info "Your FastAPI application is now running on Google Cloud Run!"
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -p, --project ID    Google Cloud Project ID"
    echo "  -r, --region        Google Cloud region (default: us-central1)"
    echo "  -s, --service       Service name (default: whatsapp-automation)"
    echo "  -t, --tag           Docker image tag (default: timestamp)"
    echo "  --skip-tests        Skip running tests"
    echo "  --skip-cleanup      Skip cleanup of old images"
    echo ""
    echo "Environment Variables:"
    echo "  GOOGLE_CLOUD_PROJECT  Google Cloud Project ID"
    echo "  REGION               Google Cloud region"
    echo "  SERVICE_NAME         Service name"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy with defaults"
    echo "  $0 -p my-project-id                   # Deploy to specific project"
    echo "  $0 --skip-tests                       # Deploy without running tests"
}

# Parse command line arguments
SKIP_TESTS=false
SKIP_CLEANUP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -p|--project)
            PROJECT_ID="$2"
            shift 2
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -s|--service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Update IMAGE_NAME with new PROJECT_ID
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Run main function
main 