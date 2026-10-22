"""Configuration. Defaults mirror the paths in the GovHealth-SLM project with full environment variable overrides."""
from __future__ import annotations
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    # Search current directory, backend directory, and project root for .env
    for candidate_env in [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]:
        if candidate_env.exists():
            load_dotenv(candidate_env, override=False)
except ImportError:
    pass

def project_path() -> Path:
    return Path(os.getenv("PROJECT_PATH", str(Path(__file__).resolve().parent.parent.parent)))

def master_path() -> Path:
    env_p = os.getenv("MASTER_PATH")
    if env_p and Path(env_p).exists():
        return Path(env_p)

    # Auto-detect existing master CSV on local disk if env path is missing or invalid
    repo_root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        repo_root / "healthcare_master_final_v3.csv",
        repo_root / "healthcare_master_final_v3 (1).csv",
        project_path() / "healthcare_master_final_v3.csv",
        project_path() / "healthcare_master_final_v3 (1).csv",
        Path("C:/sbproject/ai-sarthi/healthcare_master_final_v3.csv"),
        Path("C:/sbproject/ai-sarthi/healthcare_master_final_v3 (1).csv"),
        project_path() / "data/processed/healthcare_master_final_v3.csv",
    ]
    for c in candidates:
        if c.exists():
            return c

    return Path(env_p) if env_p else repo_root / "healthcare_master_final_v3.csv"

def adapter_path() -> Path:
    return Path(os.getenv("ADAPTER_PATH", project_path() / "models/GovHealth-SLM-Qwen3-1.7B-QLoRA-Final"))

def base_model_id() -> str:
    return os.getenv("BASE_MODEL_ID") or os.getenv("BASE_MODEL", "Qwen/Qwen3-1.7B")

# Legacy compatibility alias
BASE_MODEL = base_model_id()

def model_enabled() -> bool:
    val = os.getenv("MODEL_ENABLED")
    if val is not None:
        return val.strip().lower() in ("1", "true", "yes", "on")
    # Fallback to legacy LOAD_MODEL
    return os.getenv("LOAD_MODEL", "0").strip().lower() in ("1", "true", "yes", "on")

# Legacy compatibility alias
def load_model_enabled() -> bool:
    return model_enabled()

def model_device() -> str:
    return os.getenv("MODEL_DEVICE", "auto").strip().lower()

def model_max_new_tokens() -> int:
    val = os.getenv("MODEL_MAX_NEW_TOKENS") or os.getenv("MAX_NEW_TOKENS", "250")
    try:
        parsed = int(val)
        return max(16, min(parsed, 1024))
    except (ValueError, TypeError):
        return 250

def max_new_tokens() -> int:
    return model_max_new_tokens()

def model_temperature() -> float:
    val = os.getenv("MODEL_TEMPERATURE", "0.1")
    try:
        parsed = float(val)
        return max(0.0, min(parsed, 1.0))
    except (ValueError, TypeError):
        return 0.1

def strict_model_required() -> bool:
    return os.getenv("STRICT_MODEL_REQUIRED", "0").strip().lower() in ("1", "true", "yes", "on")

def primary_provider() -> str:
    explicit = os.getenv("PRIMARY_PROVIDER")
    if explicit:
        return explicit.strip().lower()
    # Default to openrouter if configured with an API key, else hosted
    if openrouter_enabled() and openrouter_api_key():
        return "openrouter"
    return "hosted"

def openrouter_api_key() -> str | None:
    val = os.getenv("OPENROUTER_API_KEY")
    if val and val.strip():
        return val.strip()
    return None

def openrouter_enabled() -> bool:
    val = os.getenv("OPENROUTER_ENABLED")
    if val is not None:
        return val.strip().lower() in ("1", "true", "yes", "on")
    # Automatically enabled if an API key is present
    return bool(openrouter_api_key())

def openrouter_model() -> str:
    return os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001").strip()

def openrouter_timeout() -> float:
    try:
        return max(2.0, min(float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "25")), 120.0))
    except (ValueError, TypeError):
        return 25.0

def openrouter_cooldown() -> float:
    try:
        return max(5.0, min(float(os.getenv("OPENROUTER_COOLDOWN_SECONDS", "60")), 600.0))
    except (ValueError, TypeError):
        return 60.0

def openrouter_max_retries() -> int:
    try:
        return max(0, min(int(os.getenv("OPENROUTER_MAX_RETRIES", "2")), 5))
    except (ValueError, TypeError):
        return 2

def openrouter_max_tokens() -> int:
    val = os.getenv("OPENROUTER_MAX_TOKENS")
    if val:
        try:
            return max(64, min(int(val), 2048))
        except (ValueError, TypeError):
            pass
    return max(600, model_max_new_tokens())

def openrouter_base_url() -> str:
    return os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip().rstrip("/")

def openrouter_site_url() -> str:
    return os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173").strip()

def openrouter_app_title() -> str:
    return os.getenv("OPENROUTER_APP_TITLE", "AI Sarthi GovHealth Intelligence").strip()

def hosted_model_enabled() -> bool:
    val = os.getenv("HOSTED_MODEL_ENABLED")
    if val is not None:
        return val.strip().lower() in ("1", "true", "yes", "on")
    # Default to enabled if url is set or fallback to true by default
    return True

def hosted_model_url() -> str:
    url = os.getenv("HOSTED_MODEL_URL", "https://sush2306-ai-sarthi-govhealth.hf.space")
    return url.strip().rstrip("/")

def hosted_model_timeout() -> float:
    try:
        return max(2.0, min(float(os.getenv("HOSTED_MODEL_TIMEOUT_SECONDS", "15")), 120.0))
    except (ValueError, TypeError):
        return 15.0

def hosted_model_cooldown() -> float:
    try:
        return max(5.0, min(float(os.getenv("HOSTED_MODEL_COOLDOWN_SECONDS", "60")), 600.0))
    except (ValueError, TypeError):
        return 60.0

def local_model_enabled() -> bool:
    val = os.getenv("LOCAL_MODEL_ENABLED")
    if val is not None:
        return val.strip().lower() in ("1", "true", "yes", "on")
    return model_enabled()

def local_model_path() -> Path:
    val = os.getenv("LOCAL_MODEL_PATH")
    if val:
        return Path(val)
    return adapter_path()

def local_model_runtime() -> str:
    return os.getenv("LOCAL_MODEL_RUNTIME", "transformers").strip().lower()

def fallback_enabled() -> bool:
    return os.getenv("FALLBACK_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")

def cors_origins() -> list[str]:
    return [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

def validate_model_config() -> dict[str, str | bool | int | float]:
    """Inspect and validate model configuration settings."""
    ad_path = local_model_path()
    return {
        "primary_provider": primary_provider(),
        "openrouter_enabled": openrouter_enabled(),
        "openrouter_configured": bool(openrouter_api_key()),
        "openrouter_model": openrouter_model(),
        "openrouter_timeout": openrouter_timeout(),
        "hosted_model_enabled": hosted_model_enabled(),
        "hosted_model_url": hosted_model_url(),
        "hosted_model_timeout": hosted_model_timeout(),
        "local_model_enabled": local_model_enabled(),
        "model_enabled": model_enabled(),
        "base_model_id": base_model_id(),
        "adapter_path": str(ad_path),
        "adapter_exists": ad_path.exists(),
        "model_device": model_device(),
        "max_new_tokens": model_max_new_tokens(),
        "temperature": model_temperature(),
        "strict_required": strict_model_required(),
        "fallback_enabled": fallback_enabled(),
    }

SCHEMES_FILE = Path(__file__).parent / "schemes.json"
