#!/usr/bin/env python3
"""
FastAPI WhatsApp Automation - Run Service
Simple script to start the FastAPI application
"""

import os
import sys
import uvicorn
from pathlib import Path

def main():
    # Add src to Python path
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))
    
    # Set environment variables if not set
    if not os.getenv("PYTHONPATH"):
        os.environ["PYTHONPATH"] = str(Path(__file__).parent)
    
    print("🚀 Starting FastAPI WhatsApp Automation Service...")
    print("📍 Application: http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    print("❤️  Health Check: http://localhost:8000/health")
    print("")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    # Start the application
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main() 