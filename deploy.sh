#!/bin/bash

# RADIUS Service Deployment Script

set -e

echo "🚀 RADIUS Service Deployment Script"
echo "=================================="

# Check if Docker is available
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "✅ Docker detected - deploying with containers"
    
    # Generate secure API key if not set
    if [ -z "$API_KEY" ]; then
        export API_KEY=$(openssl rand -hex 32)
        echo "🔑 Generated API Key: $API_KEY"
        echo "Please save this key securely!"
    fi
    
    echo "🐳 Starting services with Docker Compose..."
    docker-compose up -d
    
    echo "⏳ Waiting for services to be ready..."
    sleep 30
    
    echo "🔍 Checking service health..."
    curl -f http://localhost:8000/health || echo "❌ API service not ready"
    
    echo "✅ Deployment complete!"
    echo "📚 API Documentation: http://localhost:8000/docs"
    echo "🔑 API Key: $API_KEY"
    
else
    echo "⚠️  Docker not available - deploying in test mode"
    
    # Set up Python environment
    cd api-service
    
    if [ ! -d "venv" ]; then
        echo "🐍 Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    echo "📦 Installing dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
    
    # Set API key
    export API_KEY="${API_KEY:-test-bearer-token-123}"
    
    echo "🚀 Starting API service in test mode..."
    echo "🔑 API Key: $API_KEY"
    echo "📚 API Documentation: http://localhost:8000/docs"
    echo "💡 Note: Running in test mode (no database)"
    echo ""
    echo "Press Ctrl+C to stop the service"
    
    python test_app.py
fi