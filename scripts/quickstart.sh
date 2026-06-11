#!/usr/bin/env bash
# ============================================================================
# Synapse AI Gateway — Linux/macOS quickstart
#
# Usage:
#   scripts/quickstart.sh                # idempotent — safe to run repeatedly
#   scripts/quickstart.sh --reset        # wipe postgres data volume; keep .env
#   scripts/quickstart.sh --reconfigure  # delete .env and re-prompt for secrets
#   scripts/quickstart.sh --help         # show this help
# ============================================================================
set -euo pipefail

# ─── colours (only if stdout is a TTY) ──────────────────────────────────────
if [[ -t 1 ]]; then
    RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
    BLUE=$'\033[0;34m'; BOLD=$'\033[1m'; NC=$'\033[0m'
else
    RED=""; GREEN=""; YELLOW=""; BLUE=""; BOLD=""; NC=""
fi
info() { printf "%s[INFO]%s  %s\n"  "$BLUE"   "$NC" "$*"; }
ok()   { printf "%s[ OK ]%s  %s\n"  "$GREEN"  "$NC" "$*"; }
warn() { printf "%s[WARN]%s  %s\n"  "$YELLOW" "$NC" "$*"; }
err()  { printf "%s[ERR ]%s  %s\n"  "$RED"    "$NC" "$*" >&2; }
die()  { err "$*"; exit 1; }

# ─── locate repo root (the directory containing docker-compose.yml) ─────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# ─── parse args ─────────────────────────────────────────────────────────────
RESET=false
RECONFIGURE=false
for arg in "$@"; do
    case "$arg" in
        --reset)        RESET=true ;;
        --reconfigure)  RECONFIGURE=true ;;
        --help|-h)
            sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) die "Unknown argument: $arg (try --help)" ;;
    esac
done

# ─── 1. prerequisites ──────────────────────────────────────────────────────
info "Checking prerequisites…"
command -v docker >/dev/null 2>&1 \
    || die "docker not found. Install Docker Desktop (Mac) or Docker Engine (Linux)."
docker info >/dev/null 2>&1 \
    || die "Docker daemon is not running. Start Docker Desktop, or 'sudo systemctl start docker'."
docker compose version >/dev/null 2>&1 \
    || die "Docker Compose v2 not found. Update Docker Desktop, or install docker-compose-plugin."
command -v curl >/dev/null 2>&1 \
    || die "curl not found. Install with 'apt install curl' / 'brew install curl'."
ok "prerequisites OK ($(docker --version), $(docker compose version | head -1))"

# ─── 2. .env ───────────────────────────────────────────────────────────────
# --reconfigure: drop the existing .env so the prompt block runs again.
if $RECONFIGURE && [[ -f .env ]]; then
    warn "--reconfigure: deleting current .env so secrets can be re-entered…"
    rm -f .env
fi

FIRST_RUN=false
if [[ ! -f .env ]]; then
    [[ -f .env.example ]] || die ".env.example not found — run this script from the repo root."
    info "Creating .env from .env.example…"
    cp .env.example .env
    FIRST_RUN=true
else
    info ".env already present — leaving it untouched (use --reset to wipe data)"
fi

# ─── 3. prompt for required values (first run only, idempotent thereafter) ─
gen_secret() {
    python3 -c 'import secrets; print(secrets.token_hex(32))' 2>/dev/null \
        || openssl rand -hex 32 2>/dev/null \
        || head -c 64 /dev/urandom | xxd -p -c 64 2>/dev/null \
        || echo "REPLACE_WITH_64_CHAR_RANDOM_HEX_BEFORE_PROD"
}

prompt_var() {
    # prompt_var VAR_NAME description default
    local var="$1" desc="$2" default="$3" answer
    printf '\n  %s%s%s\n  %s [%s]: ' "$BOLD" "$var" "$NC" "$desc" "$default"
    read -r answer
    answer="${answer:-$default}"
    # Strip any existing entry (commented or not), then append.
    sed -E -i.bak "/^#?[[:space:]]*${var}=/d" .env && rm -f .env.bak
    printf '%s=%s\n' "$var" "$answer" >> .env
}

if $FIRST_RUN; then
    info "Set the minimum-required values (press ENTER to accept the default in brackets):"
    prompt_var JWT_SECRET        "JWT signing secret — anyone with this can forge admin tokens" "$(gen_secret)"
    prompt_var ADMIN_PASSWORD    "Initial admin password (forced change on first login)"        "synapse"
    prompt_var POSTGRES_PASSWORD "Postgres password"                                            "postgres"
    echo
fi

# ─── 4. optional reset ─────────────────────────────────────────────────────
if $RESET; then
    warn "Reset requested — tearing down stack and wiping volumes…"
    docker compose down -v --remove-orphans
    ok "stack and volumes removed"
fi

# ─── 5. bring up stack ─────────────────────────────────────────────────────
info "Building images and starting services (first run can take several minutes)…"
if ! docker compose up -d --build; then
    err "docker compose up failed."
    err "Try:  docker compose logs --tail=50"
    exit 1
fi
ok "containers started"

# ─── 6. wait for health (max 60s) ──────────────────────────────────────────
info "Waiting for the gateway to become healthy (max 60s)…"
GATEWAY_URL="http://localhost:8080"
deadline=$(( SECONDS + 60 ))
healthy=false
while (( SECONDS < deadline )); do
    if curl -fsS -m 2 "$GATEWAY_URL/" >/dev/null 2>&1; then
        healthy=true; break
    fi
    sleep 2
done
if ! $healthy; then
    err "Gateway did not become healthy within 60 seconds."
    err "Logs:  docker compose logs backend --tail=80"
    exit 1
fi
ok "gateway is up"

# ─── 7. smoke test ─────────────────────────────────────────────────────────
info "Running a sample API call…"
RESP="$(curl -fsS "$GATEWAY_URL/")"
printf "  response: %s\n" "$RESP"
echo "$RESP" | grep -q '"status":"ok"' \
    || die "Health endpoint returned an unexpected payload."
ok "gateway responding cleanly"

# ─── 8. tell the operator what to do next ──────────────────────────────────
cat <<EOF

${GREEN}${BOLD}┌────────────────────────────────────────────────────────────────────┐${NC}
${GREEN}${BOLD}│  Synapse AI Gateway is running                                     │${NC}
${GREEN}${BOLD}└────────────────────────────────────────────────────────────────────┘${NC}

  Admin console:   http://localhost:5173
  Gateway API:     http://localhost:8080
  API docs:        http://localhost:8080/docs

  First login:     admin / <ADMIN_PASSWORD from .env>
                   (admin is forced to change the password on first login)

  Create your first team API key:
    1. Open http://localhost:5173 and log in as admin
    2. Go to Teams → Add Team
    3. The api_key is shown ONCE in the create dialog — copy it now

  Sample chat completion (replace <TEAM_API_KEY>):
    curl -X POST http://localhost:8080/v1/chat/completions \\
      -H "Authorization: Bearer <TEAM_API_KEY>" \\
      -H "Content-Type: application/json" \\
      -d '{"model":"llama3.2:latest",
           "messages":[{"role":"user","content":"hello"}]}'

  Stop the stack:     docker compose down
  Wipe everything:    $(basename "$0") --reset
EOF
