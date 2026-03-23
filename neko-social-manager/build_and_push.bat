@echo off
REM -------------------------------------------------------
REM  NEKO Bot – Docker Build & Push (Windows)
REM  Voraussetzung: Docker Desktop läuft, docker login gemacht
REM -------------------------------------------------------

set IMAGE=dhoxha/neko-social-manager:latest

echo [1/3] Buildx-Builder einrichten (einmalig)...
docker buildx create --name neko-builder --use 2>nul || docker buildx use neko-builder

echo [2/3] Multi-Platform Image bauen und pushen (amd64 + arm64)...
docker buildx build --platform linux/amd64,linux/arm64 -t %IMAGE% --push .

echo [3/3] Fertig! Image verfuegbar: %IMAGE%
echo.
echo Auf dem Mac:
echo   1. .env Datei in ein Verzeichnis legen
echo   2. docker-compose.yml in dasselbe Verzeichnis kopieren
echo   3. docker-compose up -d
pause
