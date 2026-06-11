@echo off
REM ============================================================================
REM Synapse AI Gateway - Windows quickstart
REM
REM Usage:
REM   scripts\quickstart.bat                 idempotent - safe to run repeatedly
REM   scripts\quickstart.bat --reset         wipe postgres data volume; keep .env
REM   scripts\quickstart.bat --reconfigure   delete .env and re-prompt for secrets
REM   scripts\quickstart.bat --help          show this help
REM ============================================================================
setlocal

REM Resolve repo root (this script lives in <root>\scripts\).
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." >nul

REM ---- args ---------------------------------------------------------------
set "RESET=false"
set "RECONFIGURE=false"
:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--reset"       ( set "RESET=true" & shift & goto parse_args )
if /I "%~1"=="--reconfigure" ( set "RECONFIGURE=true" & shift & goto parse_args )
if /I "%~1"=="--help"        goto help
if /I "%~1"=="-h"            goto help
echo [ERR ] Unknown argument: %~1
goto fail
:help
echo Usage: scripts\quickstart.bat [--reset] [--reconfigure]
echo   --reset         Wipe the postgres data volume; keep .env.
echo   --reconfigure   Delete .env and re-prompt for secrets.
echo   --help          Show this help.
popd >nul
endlocal & exit /b 0
:args_done

REM ---- 1. prerequisites ---------------------------------------------------
echo [INFO]  Checking prerequisites...
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERR ] docker not found. Install Docker Desktop for Windows.
    goto fail
)
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERR ] Docker daemon is not running. Start Docker Desktop and re-run.
    goto fail
)
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERR ] Docker Compose v2 not found. Update Docker Desktop.
    goto fail
)
where curl >nul 2>&1
if errorlevel 1 (
    echo [ERR ] curl not found. Windows 10+ ships with curl; otherwise install it.
    goto fail
)
echo [ OK ]  prerequisites OK

REM ---- 2. .env ------------------------------------------------------------
REM --reconfigure: drop the existing .env so the prompt block runs again.
if /I "%RECONFIGURE%"=="true" if exist ".env" (
    echo [WARN]  --reconfigure: deleting current .env so secrets can be re-entered...
    del /Q .env
)

set "FIRST_RUN=false"
if not exist ".env" (
    if not exist ".env.example" (
        echo [ERR ] .env.example not found - run this script from the repo root.
        goto fail
    )
    echo [INFO]  Creating .env from .env.example...
    copy /Y .env.example .env >nul
    set "FIRST_RUN=true"
) else (
    echo [INFO]  .env already present - leaving it untouched ^(use --reset to wipe data^)
)

REM ---- 3. prompt for required values (first run only) ---------------------
if /I not "%FIRST_RUN%"=="true" goto skip_prompts

REM Try to generate a random hex via python; fallback to a clearly-placeholder.
set "DEFAULT_JWT="
for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_hex(32))" 2^>nul') do set "DEFAULT_JWT=%%i"
if not defined DEFAULT_JWT (
    for /f "delims=" %%i in ('py -3 -c "import secrets; print(secrets.token_hex(32))" 2^>nul') do set "DEFAULT_JWT=%%i"
)
if not defined DEFAULT_JWT set "DEFAULT_JWT=REPLACE_WITH_64_CHAR_RANDOM_HEX_BEFORE_PROD"

echo.
echo [INFO]  Set the minimum-required values ^(press ENTER for the default in brackets^):
echo.

echo   JWT_SECRET
echo   JWT signing secret - anyone with this can forge admin tokens
set "JWT_VAL="
set /p "JWT_VAL=    [%DEFAULT_JWT%]: "
if not defined JWT_VAL set "JWT_VAL=%DEFAULT_JWT%"

echo.
echo   ADMIN_PASSWORD
echo   Initial admin password ^(forced change on first login^)
set "ADMIN_DEFAULT=ChangeMe_At_First_Login_123!"
set "ADMIN_VAL="
set /p "ADMIN_VAL=    [%ADMIN_DEFAULT%]: "
if not defined ADMIN_VAL set "ADMIN_VAL=%ADMIN_DEFAULT%"

echo.
echo   POSTGRES_PASSWORD
echo   Postgres password
set "PG_VAL="
set /p "PG_VAL=    [postgres]: "
if not defined PG_VAL set "PG_VAL=postgres"

REM Append (compose reads the last assignment, so this overrides the commented
REM placeholders inherited from .env.example).
>>.env echo.
>>.env echo JWT_SECRET=%JWT_VAL%
>>.env echo ADMIN_PASSWORD=%ADMIN_VAL%
>>.env echo POSTGRES_PASSWORD=%PG_VAL%
echo.

:skip_prompts

REM ---- 4. optional reset --------------------------------------------------
if /I "%RESET%"=="true" (
    echo [WARN]  Reset requested - tearing down stack and wiping volumes...
    docker compose down -v --remove-orphans
    if errorlevel 1 (
        echo [ERR ] docker compose down failed.
        goto fail
    )
    echo [ OK ]  stack and volumes removed
)

REM ---- 5. bring up stack --------------------------------------------------
echo [INFO]  Building images and starting services ^(first run can take several minutes^)...
docker compose up -d --build
if errorlevel 1 (
    echo [ERR ] docker compose up failed.
    echo        Inspect with:   docker compose logs --tail=50
    goto fail
)
echo [ OK ]  containers started

REM ---- 6. wait for health (max 60s, polling every 2s) --------------------
echo [INFO]  Waiting for the gateway to become healthy ^(max 60s^)...
set "GATEWAY_URL=http://localhost:8080"
set "ATTEMPTS=0"
:wait_loop
curl -fsS -m 2 "%GATEWAY_URL%/" >nul 2>&1
if not errorlevel 1 goto healthy
set /a "ATTEMPTS+=1"
if %ATTEMPTS% GEQ 30 (
    echo [ERR ] Gateway did not become healthy within 60 seconds.
    echo        Logs:  docker compose logs backend --tail=80
    goto fail
)
REM `ping` ~= sleep, and unlike `timeout` it works when stdin is redirected.
ping -n 3 127.0.0.1 >nul
goto wait_loop
:healthy
echo [ OK ]  gateway is up

REM ---- 7. smoke test ------------------------------------------------------
echo [INFO]  Running a sample API call...
curl -fsS "%GATEWAY_URL%/"
echo.
echo [ OK ]  gateway responding cleanly

REM ---- 8. next-steps banner -----------------------------------------------
echo.
echo +---------------------------------------------------------------------+
echo ^|  Synapse AI Gateway is running                                      ^|
echo +---------------------------------------------------------------------+
echo.
echo   Admin console:   http://localhost:5173
echo   Gateway API:     http://localhost:8080
echo   API docs:        http://localhost:8080/docs
echo.
echo   First login:     admin / [ADMIN_PASSWORD from .env]
echo                    ^(admin is forced to change the password on first login^)
echo.
echo   Create your first team API key:
echo     1. Open http://localhost:5173 and log in as admin
echo     2. Go to Teams -^> Add Team
echo     3. The api_key is shown ONCE in the create dialog - copy it now
echo.
echo   Sample chat completion ^(replace [TEAM_API_KEY]^):
echo     curl -X POST http://localhost:8080/v1/chat/completions -H "Authorization: Bearer [TEAM_API_KEY]" -H "Content-Type: application/json" -d "{\"model\":\"llama3.2:latest\",\"messages\":[{\"role\":\"user\",\"content\":\"hello\"}]}"
echo.
echo   Stop the stack:     docker compose down
echo   Wipe everything:    scripts\quickstart.bat --reset
echo.

popd >nul
endlocal & exit /b 0

:fail
popd >nul
endlocal & exit /b 1
