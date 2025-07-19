#!/bin/bash

# Simple Cloud Run Deployment Script
# Quick deployment without complex validation

set -e

# Configuration
PROJECT_ID="${PROJECT_ID:-your-project-id}"
SERVICE_NAME="leva-assistant"
REGION="${REGION:-us-central1}"

echo "🚀 Deploying to Cloud Run..."
echo "Project: $PROJECT_ID"
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"

# Set project
gcloud config set project "$PROJECT_ID"

# Deploy
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --max-instances 10 \
    --timeout 300 \
    --port 8080

echo "✅ Deployment completed!"
echo "🌐 Service URL will be displayed above." 