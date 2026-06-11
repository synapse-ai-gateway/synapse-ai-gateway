@echo off
REM ============================================================================
REM Synapse AI Gateway - start the stack
REM
REM Brings up postgres + backend + frontend, waits for the gateway to become
REM healthy, prints the URLs.
REM
REM For first-time setup or to change secrets, use:
REM     scripts\quickstart.bat
REM ============================================================================
setlocal

REM ---- prereq: docker daemon ----------------------------------------------
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERR ]  Docker daemon is not running. Start Docker Desktop and try again.
    endlocal & exit /b 1
)

REM ---- bring stack up ------------------------------------------------------
echo [INFO]  Bringing the stack up...
docker compose up -d
if errorlevel 1 (
    echo [ERR ]  docker compose up failed.
    echo         Inspect: docker compose logs --tail=50
    endlocal & exit /b 1
)

REM ---- wait for backend health (max 60s) ---------------------------------
echo [INFO]  Waiting for the gateway to become healthy ^(max 60s^)...
set "ATTEMPTS=0"
:wait_loop
curl -fsS -m 2 http://localhost:8080/ >nul 2>&1
if not errorlevel 1 goto healthy
set /a "ATTEMPTS+=1"
if %ATTEMPTS% GEQ 30 (
    echo [ERR ]  Gateway did not become healthy within 60 seconds.
    echo         Inspect: docker compose logs backend --tail=80
    endlocal & exit /b 1
)
REM `ping` doubles as a stdin-redirection-safe sleep.
ping -n 3 127.0.0.1 >nul
goto wait_loop

:healthy
echo [ OK ]  gateway is up.
echo.
echo   Admin console:   http://localhost:5173
echo   Gateway API:     http://localhost:8080
echo   API docs:        http://localhost:8080/docs
echo.
echo   Stop the stack:    stop.bat
echo   Wipe everything:   scripts\quickstart.bat --reset
echo.
endlocal & exit /b 0
