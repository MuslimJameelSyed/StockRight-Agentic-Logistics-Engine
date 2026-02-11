@echo off
REM ============================================================================
REM Warehouse Putaway System - Local Deployment Setup Script (Windows)
REM ============================================================================

echo.
echo ================================================================================
echo   WAREHOUSE PUTAWAY SYSTEM - LOCAL DEPLOYMENT SETUP
echo ================================================================================
echo.

REM Check if Docker is installed
echo [1/7] Checking Docker installation...
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not installed or not in PATH
    echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo [OK] Docker is installed
echo.

REM Check if Python is installed
echo [2/7] Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.12+ from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python is installed
echo.

REM Start Docker containers
echo [3/7] Starting Docker containers (MySQL + Ollama)...
docker-compose up -d
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to start Docker containers
    pause
    exit /b 1
)
echo [OK] Docker containers started
echo.

REM Wait for MySQL to be ready
echo [4/7] Waiting for MySQL to initialize (30 seconds)...
timeout /t 30 /nobreak >nul
echo [OK] MySQL should be ready
echo.

REM Download Ollama model
echo [5/7] Downloading Ollama model (llama3.2)...
echo This may take 10-30 minutes depending on your internet connection...
docker exec warehouse-ollama ollama pull llama3.2
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Model download failed. You can download it later with:
    echo   docker exec warehouse-ollama ollama pull llama3.2
) else (
    echo [OK] Model downloaded successfully
)
echo.

REM Install Python dependencies
echo [6/7] Installing Python dependencies...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install Python dependencies
    pause
    exit /b 1
)
echo [OK] Python dependencies installed
echo.

REM Check .env file
echo [7/7] Checking environment configuration...
if not exist .env (
    echo [WARNING] .env file not found
    echo Copying .env.example to .env...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit .env file and add your:
    echo   - QDRANT_URL
    echo   - QDRANT_API_KEY
    echo   - MySQL passwords if you changed them
    echo.
) else (
    echo [OK] .env file exists
)
echo.

echo ================================================================================
echo   SETUP COMPLETE!
echo ================================================================================
echo.
echo Next steps:
echo   1. Make sure .env file has your Qdrant credentials
echo   2. Import your MySQL database (if needed):
echo      docker exec -i warehouse-mysql mysql -uroot -pwarehouse_root_2024 mydatabase_gdpr ^< data\warehouse_dump.sql
echo   3. Run the CLI version:
echo      python warehouse_chat_local_ollama.py 600
echo   4. Or run the web interface:
echo      streamlit run app_local.py
echo.
echo To stop the system:
echo   docker-compose down
echo.
echo To view logs:
echo   docker-compose logs
echo.
pause
