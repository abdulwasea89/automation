#!/bin/bash

# Cloud Run Deployment Script
# This script deploys the FastAPI app to Google Cloud Run

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_status "Checking prerequisites..."

if ! command_exists gcloud; then
    print_error "gcloud CLI is not installed. Please install it first:"
    echo "https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if ! command_exists docker; then
    print_error "Docker is not installed. Please install it first:"
    echo "https://docs.docker.com/get-docker/"
    exit 1
fi

# Configuration
PROJECT_ID="${PROJECT_ID:-your-project-id}"  # Can be set via environment variable
SERVICE_NAME="leva-assistant"
REGION="${REGION:-us-central1}"  # Can be set via environment variable

# Validate project ID
if [ "$PROJECT_ID" = "your-project-id" ]; then
    print_error "Please set PROJECT_ID environment variable or update the script"
    echo "Example: export PROJECT_ID=your-actual-project-id"
    exit 1
fi

# Set the project
print_status "Setting Google Cloud project to: $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    print_error "You are not authenticated with gcloud. Please run:"
    echo "gcloud auth login"
    exit 1
fi

# Enable required APIs
print_status "Enabling required Google Cloud APIs..."
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Environment variables validation
print_status "Validating environment variables..."

# Required environment variables
REQUIRED_VARS=(
    "OPENAI_API_KEY"
    "SHOPIFY_API_KEY"
    "SHOPIFY_API_PASSWORD"
    "SHOPIFY_STORE_NAME"
    "ZOKO_API_KEY"
)

MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    print_warning "The following environment variables are not set:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    echo ""
    print_warning "You can set them now or they will use placeholder values for testing."
    read -p "Continue with deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Deployment cancelled."
        exit 0
    fi
fi

# Set environment variables with defaults if not provided
export OPENAI_API_KEY="${OPENAI_API_KEY:-your-openai-api-key}"
export SHOPIFY_API_KEY="${SHOPIFY_API_KEY:-your-shopify-api-key}"
export SHOPIFY_API_PASSWORD="${SHOPIFY_API_PASSWORD:-your-shopify-api-password}"
export SHOPIFY_STORE_NAME="${SHOPIFY_STORE_NAME:-your-shopify-store-name}"
export ZOKO_API_KEY="${ZOKO_API_KEY:-your-zoko-api-key}"
export ZOKO_API_URL="${ZOKO_API_URL:-https://api.zoko.io}"
export ENVIRONMENT="${ENVIRONMENT:-production}"
export CACHE_TTL="${CACHE_TTL:-3600}"
export RATE_LIMIT="${RATE_LIMIT:-30}"
export RATE_PERIOD="${RATE_PERIOD:-60}"
export ENABLE_IMAGE_VALIDATION="${ENABLE_IMAGE_VALIDATION:-false}"
export ENABLE_DETAILED_LOGGING="${ENABLE_DETAILED_LOGGING:-false}"
export MAX_DB_SCAN_LIMIT="${MAX_DB_SCAN_LIMIT:-50}"
export MEMORY_SUMMARY_INTERVAL="${MEMORY_SUMMARY_INTERVAL:-5}"

print_status "Deploying to Cloud Run..."
echo "Project ID: $PROJECT_ID"
echo "Service Name: $SERVICE_NAME"
echo "Region: $REGION"
echo "Environment: $ENVIRONMENT"

# Build and deploy to Cloud Run
print_status "Building and deploying to Cloud Run..."

# Deploy to Cloud Run with improved configuration
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars "PROJECT_ID=$PROJECT_ID" \
    --set-env-vars "OPENAI_API_KEY=$OPENAI_API_KEY" \
    --set-env-vars "SHOPIFY_API_KEY=$SHOPIFY_API_KEY" \
    --set-env-vars "SHOPIFY_API_PASSWORD=$SHOPIFY_API_PASSWORD" \
    --set-env-vars "SHOPIFY_STORE_NAME=$SHOPIFY_STORE_NAME" \
    --set-env-vars "ZOKO_API_KEY=$ZOKO_API_KEY" \
    --set-env-vars "ZOKO_API_URL=$ZOKO_API_URL" \
    --set-env-vars "ENVIRONMENT=$ENVIRONMENT" \
    --set-env-vars "CACHE_TTL=$CACHE_TTL" \
    --set-env-vars "RATE_LIMIT=$RATE_LIMIT" \
    --set-env-vars "RATE_PERIOD=$RATE_PERIOD" \
    --set-env-vars "ENABLE_IMAGE_VALIDATION=$ENABLE_IMAGE_VALIDATION" \
    --set-env-vars "ENABLE_DETAILED_LOGGING=$ENABLE_DETAILED_LOGGING" \
    --set-env-vars "MAX_DB_SCAN_LIMIT=$MAX_DB_SCAN_LIMIT" \
    --set-env-vars "MEMORY_SUMMARY_INTERVAL=$MEMORY_SUMMARY_INTERVAL" \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --min-instances 0 \
    --timeout 300 \
    --concurrency 80 \
    --port 8080 \
    --set-cloudsql-instances "" \
    --add-cloudsql-instances "" \
    --update-env-vars "" \
    --remove-env-vars "" \
    --update-secrets "" \
    --remove-secrets "" \
    --update-labels "" \
    --remove-labels "" \
    --update-annotations "" \
    --remove-annotations "" \
    --no-traffic \
    --tag "" \
    --revision-suffix "" \
    --no-cpu-throttling \
    --execution-environment gen2

# Get the service URL
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")

print_success "Deployment completed successfully!"
echo ""
echo "🌐 Service URL: $SERVICE_URL"
echo "📊 Service Dashboard: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME"
echo ""
echo "🧪 Test endpoints:"
echo "  - Health check: $SERVICE_URL/health"
echo "  - Main endpoint: $SERVICE_URL/"
echo "  - Test endpoint: $SERVICE_URL/test"
echo ""
echo "📝 Next steps:"
echo "1. Test your service endpoints"
echo "2. Set up proper environment variables for production"
echo "3. Configure monitoring and logging"
echo "4. Set up custom domain if needed"
echo ""
print_warning "Remember to update environment variables with real values for production use!" 