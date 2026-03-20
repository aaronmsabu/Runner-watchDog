"""
Redis-backed runner registry.

Each runner is stored as a JSON blob keyed by its container name.
"""

import json
import logging
from typing import Any, Optional

import redis

from controller.config import REDIS_HOST, REDIS_PORT

logger = logging.getLogger("watchdog.db")

RUNNER_KEY_PREFIX = "runner:"

_pool = redis.ConnectionPool(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def _client() -> redis.Redis:
    """Return a Redis client from the shared connection pool."""
    return redis.Redis(connection_pool=_pool)


# ── CRUD operations ─────────────────────────────────────────────────────────

def register_runner(runner_id: str, data: dict[str, Any]) -> None:
    """Add or overwrite a runner record."""
    key = f"{RUNNER_KEY_PREFIX}{runner_id}"
    _client().set(key, json.dumps(data))
    logger.info("Registered runner %s", runner_id)


def get_runner(runner_id: str) -> Optional[dict[str, Any]]:
    """Return a single runner record, or None if missing."""
    raw = _client().get(f"{RUNNER_KEY_PREFIX}{runner_id}")
    if raw is None:
        return None
    return json.loads(raw)


def get_all_runners() -> dict[str, dict[str, Any]]:
    """Return every runner in the registry as {runner_id: metadata}."""
    client = _client()
    keys = client.keys(f"{RUNNER_KEY_PREFIX}*")
    runners: dict[str, dict[str, Any]] = {}
    for key in keys:
        runner_id = key.removeprefix(RUNNER_KEY_PREFIX)
        raw = client.get(key)
        if raw:
            runners[runner_id] = json.loads(raw)
    return runners


def update_runner_status(runner_id: str, status: str) -> None:
    """Update the status field of an existing runner record."""
    data = get_runner(runner_id)
    if data is None:
        logger.warning("Cannot update status — runner %s not found", runner_id)
        return
    data["status"] = status
    register_runner(runner_id, data)


def remove_runner(runner_id: str) -> None:
    """Delete a runner record from the registry."""
    _client().delete(f"{RUNNER_KEY_PREFIX}{runner_id}")
    logger.info("Removed runner %s from registry", runner_id)


def get_runners_by_version(version: str) -> dict[str, dict[str, Any]]:
    """Return all runners matching a specific version."""
    all_runners = get_all_runners()
    return {
        rid: data
        for rid, data in all_runners.items()
        if data.get("version") == version
    }
