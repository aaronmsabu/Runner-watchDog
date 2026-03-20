"""
Version checker — compares the fleet's current version against latest GitHub release.
"""

import logging

from controller.config import RUNNER_VERSION
from controller.github_api import get_latest_runner_version
from database.redis_client import get_all_runners

logger = logging.getLogger("watchdog.version")


def check_for_upgrade() -> tuple[bool, str]:
    """
    Check whether an upgrade is available.

    Returns
    -------
    (needs_upgrade, latest_version)
        needs_upgrade is True when the latest release differs from the
        configured RUNNER_VERSION.
    """
    latest = get_latest_runner_version()
    needs_upgrade = latest != RUNNER_VERSION
    if needs_upgrade:
        logger.warning(
            "Upgrade available: current=%s → latest=%s",
            RUNNER_VERSION,
            latest,
        )
    else:
        logger.info("Runners are up-to-date (version %s)", RUNNER_VERSION)
    return needs_upgrade, latest


def get_outdated_runners(latest_version: str) -> dict[str, dict]:
    """Return all registered runners whose version != latest_version."""
    all_runners = get_all_runners()
    outdated = {
        rid: data
        for rid, data in all_runners.items()
        if data.get("version") != latest_version
    }
    if outdated:
        logger.info(
            "Found %d outdated runner(s): %s",
            len(outdated),
            list(outdated.keys()),
        )
    return outdated
