import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
DEFAULT_RULES_PATH = CONFIG_DIR / "rules.yaml"

# Canonical environment configuration: backend/.env is the single source of truth
CANONICAL_ENV_FILE = BASE_DIR / ".env"
FALLBACK_ENV_FILE = BASE_DIR.parent / ".env"

if CANONICAL_ENV_FILE.exists():
    load_dotenv(CANONICAL_ENV_FILE, override=False)
elif FALLBACK_ENV_FILE.exists():
    load_dotenv(FALLBACK_ENV_FILE, override=False)

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=(str(CANONICAL_ENV_FILE), str(FALLBACK_ENV_FILE)),
        extra="ignore"
    )

    PROJECT_NAME: str = "Alert Fatigue Buster"
    TAGLINE: str = "Turn alert noise into actionable incidents."
    API_V1_STR: str = "/api"
    DATABASE_URL: str = "sqlite:///./alerts.db"
    WEBHOOK_SECRET: Optional[str] = None
    
    # Optional external provider credentials
    PAGERDUTY_API_KEY: Optional[str] = None
    SLACK_WEBHOOK_URL: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "alerts@alertbuster.internal"

    # Resend Email Integration (Step 3)
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"
    NOTIFICATION_EMAIL: Optional[str] = None

    # AI SRE Chatbot LLM Configuration
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    
    # Rules YAML Path
    RULES_PATH: str = str(DEFAULT_RULES_PATH)

settings = Settings()

def load_rules() -> Dict[str, Any]:
    rules_path = Path(settings.RULES_PATH)
    if rules_path.exists():
        with open(rules_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def save_rules(rules_data: Dict[str, Any]) -> None:
    rules_path = Path(settings.RULES_PATH)
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    with open(rules_path, "w", encoding="utf-8") as f:
        yaml.dump(rules_data, f, default_flow_style=False)
