@echo off
REM Quick deployment script for Store Intelligence System (Windows)

echo ==========================================
echo Store Intelligence System - Deployment
echo ==========================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed
    echo Please install Docker Desktop from https://docs.docker.com/desktop/install/windows-install/
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker Compose is not installed
    echo Please install Docker Compose
    exit /b 1
)

echo + Docker and Docker Compose are installed
echo.

REM Stop existing containers
echo Stopping existing containers...
docker-compose down 2>nul
echo.

REM Build and start services
echo Building and starting services...
docker-compose up -d --build
echo.

REM Wait for services to be ready
echo Waiting for services to be ready...
timeout /t 10 /nobreak >nul
echo.

REM Check if database is ready
echo Checking database connection...
set DB_READY=0
for /L %%i in (1,1,30) do (
    docker-compose exec -T db pg_isready -U store_user -d store_intelligence >nul 2>&1
    if not errorlevel 1 (
        echo + Database is ready
        set DB_READY=1
        goto :db_ready
    )
    timeout /t 2 /nobreak >nul
)

:db_ready
if %DB_READY%==0 (
    echo Error: Database failed to start
    docker-compose logs db
    exit /b 1
)
echo.

REM Check if API is ready
echo Checking API connection...
set API_READY=0
for /L %%i in (1,1,30) do (
    curl -s http://localhost:8000/health >nul 2>&1
    if not errorlevel 1 (
        echo + API is ready
        set API_READY=1
        goto :api_ready
    )
    timeout /t 2 /nobreak >nul
)

:api_ready
if %API_READY%==0 (
    echo Error: API failed to start
    docker-compose logs api
    exit /b 1
)
echo.

REM Initialize data
echo Initializing data...
if exist "scripts\setup_complete_system.py" (
    python scripts\setup_complete_system.py
    echo + Data initialized
) else (
    echo ! Warning: setup_complete_system.py not found, skipping data initialization
)
echo.

REM Display status
echo ==========================================
echo Deployment Complete!
echo ==========================================
echo.
echo Services are running:
echo   * API:       http://localhost:8000
echo   * API Docs:  http://localhost:8000/docs
echo   * Dashboard: http://localhost:8501
echo   * Database:  localhost:5432
echo.
echo To view logs:
echo   docker-compose logs -f
echo.
echo To stop services:
echo   docker-compose down
echo.
echo To view service status:
echo   docker-compose ps
echo.
pause
