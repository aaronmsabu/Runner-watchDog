"""
Fleet Controller — main watchdog loop.

Periodically checks for runner version updates and triggers rolling
replacements when a newer version is detected.
"""

import logging
import sys
import time

from controller.config import CHECK_INTERVAL_SECONDS, RUNNER_VERSION
from controller.runner_manager import rolling_update
from controller.version_checker import check_for_upgrade, get_outdated_runners

# ── Logging setup ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-22s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("watchdog.fleet")


# ── Core logic ───────────────────────────────────────────────────────────────

def fleet_controller() -> dict | None:
    """
    Run a single upgrade-check cycle.

    Returns a summary dict when an update was performed, or None if
    everything is up-to-date.
    """
    logger.info("──── Fleet check started (current baseline: %s) ────", RUNNER_VERSION)

    needs_upgrade, latest_version = check_for_upgrade()

    if not needs_upgrade:
        logger.info("No upgrade needed — fleet is current.")
        return None

    logger.warning("New runner version detected: %s", latest_version)

    outdated = get_outdated_runners(latest_version)

    if not outdated:
        logger.info("No outdated runners in registry — nothing to replace.")
        return None

    summary = rolling_update(outdated, latest_version)
    return summary


# ── Watchdog loop ────────────────────────────────────────────────────────────

def run_watchdog() -> None:
    """Block forever, running fleet_controller on a fixed interval."""
    logger.info(
        "Watchdog started — checking every %d seconds", CHECK_INTERVAL_SECONDS,
    )
    while True:
        try:
            fleet_controller()
        except Exception:
            logger.exception("Fleet check failed — will retry next cycle")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_watchdog()
