"""
Centralized configuration for the Runner Watchdog.

All settings are loaded from environment variables (with .env file support).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── GitHub ───────────────────────────────────────────────────────────────────
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
REPO_URL: str = os.getenv("REPO_URL", "")  # e.g. https://github.com/org/repo

# ── Redis ────────────────────────────────────────────────────────────────────
REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

# ── Runner defaults ─────────────────────────────────────────────────────────
RUNNER_VERSION: str = os.getenv("RUNNER_VERSION", "2.329.0")
RUNNER_IMAGE_NAME: str = os.getenv("RUNNER_IMAGE_NAME", "github-runner-image")

# ── Fleet controller ────────────────────────────────────────────────────────
UPDATE_BATCH_PERCENT: int = int(os.getenv("UPDATE_BATCH_PERCENT", "10"))
CHECK_INTERVAL_SECONDS: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "3600"))
