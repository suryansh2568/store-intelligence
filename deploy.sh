#!/bin/bash
# Quick deployment script for Store Intelligence System

set -e

echo "=========================================="
echo "Store Intelligence System - Deployment"
echo "=========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    echo "Please install Docker from https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    echo "Please install Docker Compose from https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ Docker and Docker Compose are installed"
echo ""

# Stop existing containers
echo "Stopping existing containers..."
docker-compose down 2>/dev/null || true
echo ""

# Build and start services
echo "Building and starting services..."
docker-compose up -d --build
echo ""

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 10

# Check if database is ready
echo "Checking database connection..."
for i in {1..30}; do
    if docker-compose exec -T db pg_isready -U store_user -d store_intelligence &> /dev/null; then
        echo "✓ Database is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Error: Database failed to start"
        docker-compose logs db
        exit 1
    fi
    sleep 2
done
echo ""

# Check if API is ready
echo "Checking API connection..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health &> /dev/null; then
        echo "✓ API is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Error: API failed to start"
        docker-compose logs api
        exit 1
    fi
    sleep 2
done
echo ""

# Initialize data
echo "Initializing data..."
if [ -f "scripts/setup_complete_system.py" ]; then
    python scripts/setup_complete_system.py
    echo "✓ Data initialized"
else
    echo "⚠ Warning: setup_complete_system.py not found, skipping data initialization"
fi
echo ""

# Display status
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Services are running:"
echo "  • API:       http://localhost:8000"
echo "  • API Docs:  http://localhost:8000/docs"
echo "  • Dashboard: http://localhost:8501"
echo "  • Database:  localhost:5432"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop services:"
echo "  docker-compose down"
echo ""
echo "To view service status:"
echo "  docker-compose ps"
echo ""
