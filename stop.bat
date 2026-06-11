@echo off
REM ============================================================================
REM Synapse AI Gateway - stop the stack
REM
REM Stops and removes the containers. The postgres data volume is preserved,
REM so `start.bat` afterwards picks up exactly where you left off.
REM
REM To also wipe the database (full teardown), use:
REM     scripts\quickstart.bat --reset
REM or:
REM     docker compose down -v
REM ============================================================================
setlocal

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERR ]  Docker daemon is not running.
    endlocal & exit /b 1
)

echo [INFO]  Stopping the stack...
docker compose down
if errorlevel 1 (
    echo [ERR ]  docker compose down failed.
    endlocal & exit /b 1
)

echo [ OK ]  stack stopped. Postgres data preserved.
echo.
echo   Restart:           start.bat
echo   Wipe everything:   scripts\quickstart.bat --reset
echo.
endlocal & exit /b 0
