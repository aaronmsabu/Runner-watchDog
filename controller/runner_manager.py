"""
Runner manager — provisions and removes Docker-based GitHub Actions runners.

Handles:
- Launching new runner containers
- Stopping + removing old containers
- Rolling updates in configurable batch sizes
"""

import logging
import math
import subprocess
import time
from typing import Any

from controller.config import (
    REPO_URL,
    RUNNER_IMAGE_NAME,
    UPDATE_BATCH_PERCENT,
)
from controller.github_api import get_runner_registration_token
from database.redis_client import (
    get_all_runners,
    register_runner,
    remove_runner as registry_remove,
)

logger = logging.getLogger("watchdog.manager")


# ── Provisioning ─────────────────────────────────────────────────────────────

def launch_runner(version: str) -> str:
    """
    Start a new runner container for the given version.

    Returns the container name.
    """
    token = get_runner_registration_token()
    container_name = f"runner-{version}-{int(time.time())}"

    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "-e", f"REPO_URL={REPO_URL}",
        "-e", f"RUNNER_TOKEN={token}",
        f"{RUNNER_IMAGE_NAME}:{version}",
    ]

    logger.info("Launching runner container: %s", container_name)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        logger.error("Failed to launch runner: %s", result.stderr.strip())
        raise RuntimeError(f"docker run failed: {result.stderr.strip()}")

    # Register in Redis
    register_runner(container_name, {
        "version": version,
        "host": "docker",
        "status": "active",
        "started_at": int(time.time()),
    })

    logger.info("Runner %s launched successfully", container_name)
    return container_name


# ── Removal ──────────────────────────────────────────────────────────────────

def remove_runner(container_name: str) -> None:
    """Stop and remove a runner container, then clean up the registry."""
    logger.info("Removing runner container: %s", container_name)

    # Graceful stop (sends SIGTERM → start.sh cleanup trap fires)
    subprocess.run(
        ["docker", "stop", container_name],
        capture_output=True, text=True, check=False,
    )
    subprocess.run(
        ["docker", "rm", container_name],
        capture_output=True, text=True, check=False,
    )

    registry_remove(container_name)
    logger.info("Runner %s removed", container_name)


# ── Rolling update ───────────────────────────────────────────────────────────

def rolling_update(
    outdated_runners: dict[str, dict[str, Any]],
    new_version: str,
    batch_percent: int | None = None,
) -> dict[str, Any]:
    """
    Replace outdated runners with new-version containers in batches.

    Parameters
    ----------
    outdated_runners : {container_name: metadata}
    new_version      : version string to upgrade to
    batch_percent    : % of fleet to replace per cycle (default from config)

    Returns
    -------
    Summary dict with counts of launched / removed / failed.
    """
    batch_pct = batch_percent or UPDATE_BATCH_PERCENT
    total = len(outdated_runners)
    batch_size = max(1, math.ceil(total * batch_pct / 100))

    logger.info(
        "Starting rolling update: %d outdated runner(s), batch size %d (%d%%)",
        total,
        batch_size,
        batch_pct,
    )

    launched = 0
    removed = 0
    failed = 0
    runner_names = list(outdated_runners.keys())

    for i in range(0, total, batch_size):
        batch = runner_names[i : i + batch_size]
        logger.info("Processing batch %d–%d", i + 1, i + len(batch))

        for old_name in batch:
            try:
                # 1. Launch replacement
                new_name = launch_runner(new_version)
                launched += 1

                # 2. Brief wait for the new runner to register with GitHub
                time.sleep(10)

                # 3. Tear down old runner
                remove_runner(old_name)
                removed += 1

                logger.info(
                    "Replaced %s → %s", old_name, new_name,
                )
            except Exception:
                logger.exception("Failed to replace runner %s", old_name)
                failed += 1

    summary = {
        "total_outdated": total,
        "launched": launched,
        "removed": removed,
        "failed": failed,
    }
    logger.info("Rolling update complete: %s", summary)
    return summary
