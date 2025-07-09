# Use official Python slim image
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY src/ ./src/

EXPOSE 8080

# Start Gunicorn server with increased timeout and more workers
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "src.main:app", "--bind", "0.0.0.0:8080", "--timeout", "300", "--keep-alive", "5", "--max-requests", "1000", "--max-requests-jitter", "100"]
