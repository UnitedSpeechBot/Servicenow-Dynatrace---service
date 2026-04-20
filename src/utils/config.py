"""
Configuration module – loads all secrets and settings from .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── ServiceNow ──────────────────────────────────────────────
SNOW_INSTANCE = os.getenv("SNOW_INSTANCE")
SNOW_USER = os.getenv("SNOW_USER")
SNOW_PASSWORD = os.getenv("SNOW_PASSWORD")
SNOW_BASE_URL = f"https://{SNOW_INSTANCE}.service-now.com" if SNOW_INSTANCE else ""

# ── AWS / Bedrock ───────────────────────────────────────────
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")

# ── Dynatrace ──────────────────────────────────────────────
DYNATRACE_TOKEN = os.getenv("DYNATRACE_TOKEN")
DYNATRACE_ENV_ID = os.getenv("DYNATRACE_ENV_ID", "ikw77634")

# ── GitHub ─────────────────────────────────────────────────
GH_PAT_TOKEN = os.getenv("GH_PAT_TOKEN")

# ── Jira ───────────────────────────────────────────────────
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "DEV")

# ── SMTP / Notifications ──────────────────────────────────
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT", "587")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")


# ── Startup Validation ────────────────────────────────────
def validate():
    """Call at app startup to fail fast on missing critical env vars."""
    required = {
        "SNOW_INSTANCE": SNOW_INSTANCE,
        "SNOW_USER": SNOW_USER,
        "SNOW_PASSWORD": SNOW_PASSWORD,
        "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
        "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
        "DYNATRACE_TOKEN": DYNATRACE_TOKEN,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please set them in your .env file."
        )
