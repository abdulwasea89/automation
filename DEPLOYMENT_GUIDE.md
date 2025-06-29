# 🚀 Complete FastAPI Deployment Guide: Google Cloud Run + Docker + CI/CD

This guide will walk you through deploying your WhatsApp Product Assistant FastAPI application to Google Cloud Run with Docker, CI/CD automation, and comprehensive documentation.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Structure](#project-structure)
3. [Local Development Setup](#local-development-setup)
4. [Docker Configuration](#docker-configuration)
5. [Google Cloud Setup](#google-cloud-setup)
6. [CI/CD Pipeline Setup](#cicd-pipeline-setup)
7. [Deployment](#deployment)
8. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
9. [Security Best Practices](#security-best-practices)

---

## 🔧 Prerequisites

Before starting, ensure you have:

- [Google Cloud Account](https://cloud.google.com/) with billing enabled
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) installed
- [Docker](https://docs.docker.com/get-docker/) installed
- [Git](https://git-scm.com/) installed
- [Python 3.11+](https://www.python.org/downloads/) installed

---

## 📁 Project Structure

```
automation/
├── app.py                          # Main FastAPI application
├── src/                            # Source code directory
│   ├── __init__.py
│   ├── agent_runner.py            # AI agent runner
│   ├── broadcast.py               # Broadcasting functionality
│   ├── cache.py                   # Caching utilities
│   ├── config.py                  # Configuration management
│   ├── db_agent.py                # Database agent
│   ├── deps.py                    # Dependencies
│   ├── gcp.py                     # Google Cloud Platform utilities
│   ├── handoff_tools.py           # Agent handoff tools
│   ├── main.py                    # Main application entry point
│   ├── models.py                  # Data models
│   ├── openai_agent.py            # OpenAI agent implementation
│   ├── product_showcase.py        # Product showcase functionality
│   ├── shopify_client.py          # Shopify integration
│   ├── tools.py                   # Utility tools
│   ├── zoko_client.py             # Zoko WhatsApp client
│   └── zoko_utils.py              # Zoko utilities
├── Dockerfile                     # Production Docker configuration
├── docker-compose.yml             # Local development Docker setup
├── requirements.txt               # Python dependencies
├── cloudbuild.yaml                # Google Cloud Build configuration
├── app.yaml                       # App Engine configuration (alternative)
├── deploy.sh                      # Deployment script
├── .github/                       # GitHub Actions CI/CD
│   └── workflows/
│       └── deploy.yml
├── .gitignore                     # Git ignore rules
├── README.md                      # Project documentation
├── service-account.json           # Google Cloud service account key
├── zoko_templates.json            # Zoko WhatsApp templates
└── templates.json                 # Application templates
```

---

## 🏠 Local Development Setup

### 1. Clone and Setup

```bash
# Clone your repository
git clone <your-repo-url>
cd automation

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in your project root:

```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=./service-account.json

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key

# Zoko Configuration
ZOKO_API_KEY=your-zoko-api-key
ZOKO_BASE_URL=https://api.zoko.com

# Application Configuration
DEBUG=true
LOG_LEVEL=INFO
```

### 3. Local Development with Docker

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or run directly with Python
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

---

## 🐳 Docker Configuration

Your current Dockerfile is well-optimized with multi-stage builds. Here's what it does:

### Production Dockerfile Analysis

```dockerfile
# Stage 1: Builder - Optimizes dependency installation
FROM python:3.11-bullseye as builder
# Installs build dependencies and creates virtual environment

# Stage 2: Production - Minimal runtime image
FROM python:3.11-bullseye
# Creates non-root user, copies only necessary files
# Runs with gunicorn for production
```

### Docker Compose for Development

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8080"
    environment:
      - DEBUG=true
    volumes:
      - ./src:/app/src
      - ./service-account.json:/app/service-account.json
```

---

## ☁️ Google Cloud Setup

### 1. Initialize Google Cloud

```bash
# Login to Google Cloud
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  containerregistry.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com
```

### 2. Create Service Account

```bash
# Create service account
gcloud iam service-accounts create whatsapp-automation \
  --display-name="WhatsApp Automation Service Account"

# Grant necessary roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:whatsapp-automation@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:whatsapp-automation@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:whatsapp-automation@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/firestore.user"

# Create and download key
gcloud iam service-accounts keys create service-account.json \
  --iam-account=whatsapp-automation@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 3. Configure Cloud Build

```bash
# Grant Cloud Build service account access to Cloud Run
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/storage.admin"
```

---

## 🔄 CI/CD Pipeline Setup

### GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  REGION: us-central1
  SERVICE_NAME: whatsapp-automation

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          
      - name: Run tests
        run: |
          python -m pytest tests/ -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/master'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Google Auth
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
          
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2
        
      - name: Configure Docker
        run: gcloud auth configure-docker
        
      - name: Build and Push
        run: |
          docker build -t gcr.io/$PROJECT_ID/$SERVICE_NAME:${{ github.sha }} .
          docker push gcr.io/$PROJECT_ID/$SERVICE_NAME:${{ github.sha }}
          
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy $SERVICE_NAME \
            --image gcr.io/$PROJECT_ID/$SERVICE_NAME:${{ github.sha }} \
            --region $REGION \
            --platform managed \
            --allow-unauthenticated \
            --port 8080 \
            --memory 2Gi \
            --cpu 2 \
            --max-instances 10 \
            --timeout 300 \
            --set-env-vars GOOGLE_APPLICATION_CREDENTIALS=/app/service-account.json
```

### GitHub Secrets Setup

In your GitHub repository, go to Settings > Secrets and variables > Actions, and add:

- `GCP_PROJECT_ID`: Your Google Cloud project ID
- `GCP_SA_KEY`: The entire content of your service-account.json file

---

## 🚀 Deployment

### Option 1: Manual Deployment

```bash
# Build and push to Container Registry
docker build -t gcr.io/YOUR_PROJECT_ID/whatsapp-automation:v1 .
docker push gcr.io/YOUR_PROJECT_ID/whatsapp-automation:v1

# Deploy to Cloud Run
gcloud run deploy whatsapp-automation \
  --image gcr.io/YOUR_PROJECT_ID/whatsapp-automation:v1 \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --max-instances 10 \
  --timeout 300
```

### Option 2: Cloud Build (Recommended)

```bash
# Trigger Cloud Build
gcloud builds submit --config cloudbuild.yaml
```

### Option 3: GitHub Actions (Automatic)

Simply push to your main branch, and GitHub Actions will automatically deploy.

---

## 📊 Monitoring & Troubleshooting

### 1. View Logs

```bash
# Cloud Run logs
gcloud logs read --service=whatsapp-automation --limit=50

# Real-time logs
gcloud logs tail --service=whatsapp-automation
```

### 2. Health Checks

Your application includes health endpoints:

- `GET /health` - Basic health check
- `GET /docs` - API documentation (Swagger UI)

### 3. Common Issues

#### Issue: Service Account Permissions
```bash
# Verify service account has correct permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:whatsapp-automation"
```

#### Issue: Container Build Failures
```bash
# Check build logs
gcloud builds log BUILD_ID

# Test locally first
docker build -t test-image .
docker run -p 8080:8080 test-image
```

#### Issue: Memory/CPU Limits
```bash
# Monitor resource usage
gcloud run services describe whatsapp-automation --region=us-central1

# Adjust if needed
gcloud run services update whatsapp-automation \
  --memory 4Gi \
  --cpu 4 \
  --region us-central1
```

---

## 🔒 Security Best Practices

### 1. Environment Variables

Never commit sensitive data. Use environment variables:

```python
# In your config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    ZOKO_API_KEY: str = os.getenv("ZOKO_API_KEY")
```

### 2. Service Account Security

- Use least privilege principle
- Rotate keys regularly
- Never commit service account keys to version control

### 3. Network Security

```bash
# Restrict access if needed
gcloud run services update whatsapp-automation \
  --no-allow-unauthenticated \
  --region us-central1
```

### 4. Secrets Management

For production, use Google Secret Manager:

```bash
# Create secrets
echo -n "your-api-key" | gcloud secrets create openai-api-key --data-file=-

# Grant access to Cloud Run
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:whatsapp-automation@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 📈 Scaling & Performance

### 1. Auto-scaling Configuration

```bash
# Configure auto-scaling
gcloud run services update whatsapp-automation \
  --min-instances 0 \
  --max-instances 20 \
  --concurrency 80 \
  --region us-central1
```

### 2. Performance Monitoring

```bash
# Enable monitoring
gcloud run services update whatsapp-automation \
  --enable-exec \
  --region us-central1
```

### 3. Cost Optimization

- Use `--min-instances 0` for cost savings
- Monitor usage with Cloud Console
- Set up billing alerts

---

## 🎯 Next Steps

1. **Set up monitoring**: Configure Cloud Monitoring and alerting
2. **Add custom domain**: Configure custom domain with SSL
3. **Implement caching**: Add Redis for session management
4. **Database optimization**: Optimize Firestore queries and indexes
5. **Load testing**: Test with realistic traffic patterns

---

## 📚 Additional Resources

- [FastAPI Deployment Documentation](https://fastapi.tiangolo.com/deployment/)
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

---

## 🆘 Support

If you encounter issues:

1. Check the logs: `gcloud logs read --service=whatsapp-automation`
2. Verify configuration: `gcloud run services describe whatsapp-automation`
3. Test locally: `docker-compose up --build`
4. Review this guide's troubleshooting section

Your FastAPI application is now ready for production deployment! 🎉 