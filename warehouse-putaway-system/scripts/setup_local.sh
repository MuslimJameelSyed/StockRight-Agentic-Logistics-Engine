#!/bin/bash
# ============================================================================
# Warehouse Putaway System - Local Deployment Setup Script (Linux/Mac)
# ============================================================================

set -e  # Exit on error

echo ""
echo "================================================================================"
echo "  WAREHOUSE PUTAWAY SYSTEM - LOCAL DEPLOYMENT SETUP"
echo "================================================================================"
echo ""

# Check if Docker is installed
echo "[1/7] Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed"
    echo "Please install Docker from https://www.docker.com/products/docker-desktop"
    exit 1
fi
echo "[OK] Docker is installed"
echo ""

# Check if Python is installed
echo "[2/7] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python is not installed"
    echo "Please install Python 3.12+ from https://www.python.org/downloads/"
    exit 1
fi
echo "[OK] Python is installed"
echo ""

# Start Docker containers
echo "[3/7] Starting Docker containers (MySQL + Ollama)..."
docker-compose up -d
echo "[OK] Docker containers started"
echo ""

# Wait for MySQL to be ready
echo "[4/7] Waiting for MySQL to initialize (30 seconds)..."
sleep 30
echo "[OK] MySQL should be ready"
echo ""

# Download Ollama model
echo "[5/7] Downloading Ollama model (llama3.2)..."
echo "This may take 10-30 minutes depending on your internet connection..."
if docker exec warehouse-ollama ollama pull llama3.2; then
    echo "[OK] Model downloaded successfully"
else
    echo "[WARNING] Model download failed. You can download it later with:"
    echo "  docker exec warehouse-ollama ollama pull llama3.2"
fi
echo ""

# Install Python dependencies
echo "[6/7] Installing Python dependencies..."
pip3 install -r requirements.txt
echo "[OK] Python dependencies installed"
echo ""

# Check .env file
echo "[7/7] Checking environment configuration..."
if [ ! -f .env ]; then
    echo "[WARNING] .env file not found"
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo ""
    echo "IMPORTANT: Please edit .env file and add your:"
    echo "  - QDRANT_URL"
    echo "  - QDRANT_API_KEY"
    echo "  - MySQL passwords if you changed them"
    echo ""
else
    echo "[OK] .env file exists"
fi
echo ""

echo "================================================================================"
echo "  SETUP COMPLETE!"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Make sure .env file has your Qdrant credentials"
echo "  2. Import your MySQL database (if needed):"
echo "     docker exec -i warehouse-mysql mysql -uroot -pwarehouse_root_2024 mydatabase_gdpr < data/warehouse_dump.sql"
echo "  3. Run the CLI version:"
echo "     python3 warehouse_chat_local_ollama.py 600"
echo "  4. Or run the web interface:"
echo "     streamlit run app_local.py"
echo ""
echo "To stop the system:"
echo "  docker-compose down"
echo ""
echo "To view logs:"
echo "  docker-compose logs"
echo ""
