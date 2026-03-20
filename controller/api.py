"""
FastAPI control API for the Runner Watchdog.

Endpoints let you inspect fleet state, check for updates, and manually
trigger rolling replacements.
"""

import logging
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from controller.config import RUNNER_VERSION
from controller.github_api import get_latest_runner_version, get_repo_runners
from controller.main import fleet_controller, run_watchdog
from controller.runner_manager import rolling_update
from controller.version_checker import check_for_upgrade, get_outdated_runners
from database.redis_client import get_all_runners

logger = logging.getLogger("watchdog.api")


# ── Lifespan: start the background watchdog loop ────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start the watchdog loop in a background daemon thread on startup."""
    thread = threading.Thread(target=run_watchdog, daemon=True)
    thread.start()
    logger.info("Background watchdog thread started")
    yield


app = FastAPI(
    title="Runner Watchdog API",
    description="Control plane for the self-hosted GitHub Actions runner fleet.",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


@app.get("/runners")
async def list_runners() -> dict[str, Any]:
    """List all runners from the local registry."""
    runners = get_all_runners()
    return {"count": len(runners), "runners": runners}


@app.get("/runners/github")
async def list_github_runners() -> dict[str, Any]:
    """List runners registered on GitHub for the configured repo."""
    try:
        runners = get_repo_runners()
        return {"count": len(runners), "runners": runners}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/version/latest")
async def latest_version() -> dict[str, str]:
    """Fetch the latest runner version from GitHub."""
    try:
        version = get_latest_runner_version()
        return {"latest_version": version}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/status")
async def fleet_status() -> dict[str, Any]:
    """Fleet status summary: counts by version and upgrade availability."""
    runners = get_all_runners()

    version_counts: dict[str, int] = {}
    for data in runners.values():
        v = data.get("version", "unknown")
        version_counts[v] = version_counts.get(v, 0) + 1

    try:
        needs_upgrade, latest = check_for_upgrade()
    except Exception:
        needs_upgrade, latest = None, "unavailable"

    return {
        "total_runners": len(runners),
        "baseline_version": RUNNER_VERSION,
        "latest_version": latest,
        "upgrade_available": needs_upgrade,
        "version_distribution": version_counts,
    }


@app.post("/check-update")
async def trigger_check() -> dict[str, Any]:
    """Manually trigger a version check."""
    try:
        needs_upgrade, latest = check_for_upgrade()
        return {
            "upgrade_available": needs_upgrade,
            "latest_version": latest,
            "current_version": RUNNER_VERSION,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/trigger-update")
async def trigger_update() -> JSONResponse:
    """Manually trigger a rolling update if an upgrade is available."""
    try:
        needs_upgrade, latest = check_for_upgrade()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not needs_upgrade:
        return JSONResponse(
            status_code=200,
            content={"message": "Fleet is already up-to-date", "version": latest},
        )

    outdated = get_outdated_runners(latest)
    if not outdated:
        return JSONResponse(
            status_code=200,
            content={"message": "No outdated runners found in registry"},
        )

    summary = rolling_update(outdated, latest)
    return JSONResponse(status_code=200, content=summary)
