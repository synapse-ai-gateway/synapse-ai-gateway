"""
Application configuration.

Every configurable value is read from an environment variable here, in one
place, with a sensible default. Nothing operational should be hardcoded
elsewhere in the codebase — import `settings` and read from it instead.

See .env.example for documentation of every variable.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the same directory as this file (does not override real env)
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

_BACKEND_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Typed environment readers
# ---------------------------------------------------------------------------
def _get_str(key: str, default: str) -> str:
    val = os.environ.get(key)
    return val if val is not None and val != "" else default


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _get_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = _get_str(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/synapse_ai_gateway",
    )
    DB_POOL_SIZE: int = _get_int("DB_POOL_SIZE", 10)
    DB_MAX_OVERFLOW: int = _get_int("DB_MAX_OVERFLOW", 20)
    DB_POOL_PRE_PING: bool = _get_bool("DB_POOL_PRE_PING", True)
    DB_ECHO: bool = _get_bool("DB_ECHO", False)

    # ── LLM backend (Ollama / vLLM / any OpenAI-compatible endpoint) ─────────
    VLLM_URL: str = _get_str("VLLM_URL", "http://localhost:11434/v1")
    # Optional cloud LLM endpoint used for non-sensitive routing. Empty disables
    # hybrid routing — all traffic stays on-prem.
    CLOUD_VLLM_URL: str = _get_str("CLOUD_VLLM_URL", "")
    DEFAULT_MODEL: str = _get_str("DEFAULT_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    LLM_REQUEST_TIMEOUT_SEC: int = _get_int("LLM_REQUEST_TIMEOUT_SEC", 30)
    MODELS_FETCH_TIMEOUT_SEC: float = _get_float("MODELS_FETCH_TIMEOUT_SEC", 5.0)

    # ── Outbound HTTP client tuning (gateway → LLM backend) ──────────────────
    HTTP_CONNECT_TIMEOUT_SEC: float = _get_float("HTTP_CONNECT_TIMEOUT_SEC", 5.0)
    HTTP_WRITE_TIMEOUT_SEC: float = _get_float("HTTP_WRITE_TIMEOUT_SEC", 10.0)
    HTTP_POOL_TIMEOUT_SEC: float = _get_float("HTTP_POOL_TIMEOUT_SEC", 5.0)
    HTTP_MAX_KEEPALIVE_CONNECTIONS: int = _get_int("HTTP_MAX_KEEPALIVE_CONNECTIONS", 10)
    HTTP_MAX_CONNECTIONS: int = _get_int("HTTP_MAX_CONNECTIONS", 20)

    # ── Authentication / JWT ─────────────────────────────────────────────────
    ADMIN_PASSWORD: str = _get_str("ADMIN_PASSWORD", "ChangeMe_At_First_Login_123!")
    JWT_SECRET: str = _get_str("JWT_SECRET", "change-this-to-a-32-char-random-string-now")
    JWT_ALGORITHM: str = _get_str("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_HOURS: int = _get_int("ACCESS_TOKEN_EXPIRE_HOURS", 8)
    BCRYPT_ROUNDS: int = _get_int("BCRYPT_ROUNDS", 12)
    PASSWORD_MIN_LENGTH: int = _get_int("PASSWORD_MIN_LENGTH", 12)
    TEMP_PASSWORD_LENGTH: int = _get_int("TEMP_PASSWORD_LENGTH", 16)

    # ── Security policy defaults (seed initial values into gateway_settings;
    #    also used as runtime fallbacks if a setting row is missing) ──────────
    MAX_FAILED_LOGINS: int = _get_int("MAX_FAILED_LOGINS", 5)
    LOCKOUT_MINUTES: int = _get_int("LOCKOUT_MINUTES", 30)
    INACTIVITY_DISABLE_DAYS: int = _get_int("INACTIVITY_DISABLE_DAYS", 90)
    MIN_PASSWORD_AGE_DAYS: int = _get_int("MIN_PASSWORD_AGE_DAYS", 1)
    MAX_PASSWORD_AGE_DAYS: int = _get_int("MAX_PASSWORD_AGE_DAYS", 90)
    PASSWORD_HISTORY_COUNT: int = _get_int("PASSWORD_HISTORY_COUNT", 24)
    SESSION_WARNING_MINUTES: int = _get_int("SESSION_WARNING_MINUTES", 2)
    SINGLE_SESSION_PER_USER: bool = _get_bool("SINGLE_SESSION_PER_USER", True)

    # ── Rate limiting + prompt defaults (seed initial gateway_settings) ──────
    DEFAULT_REQUESTS: int = _get_int("DEFAULT_REQUESTS", 10)
    DEFAULT_WINDOW_SEC: int = _get_int("DEFAULT_WINDOW_SEC", 60)
    DEFAULT_SYSTEM_PROMPT: str = _get_str(
        "DEFAULT_SYSTEM_PROMPT",
        "You are a helpful AI assistant for YourOrg. "
        "Answer questions clearly and professionally. "
        "Do not discuss confidential bank policies or share sensitive information.",
    )

    # ── DLP ──────────────────────────────────────────────────────────────────
    # Path to the JSON file holding the initial DLP category definitions.
    # Definitions live in external config, never in source (see CONTRIBUTING).
    DLP_PATTERNS_FILE: str = _get_str(
        "DLP_PATTERNS_FILE", str(_BACKEND_DIR / "dlp_patterns.json")
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGIN: str = _get_str("CORS_ORIGIN", "http://localhost:5173")

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = _get_str("LOG_LEVEL", "INFO")

    # Derived / convenience
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGIN.split(",")]


settings = Settings()
