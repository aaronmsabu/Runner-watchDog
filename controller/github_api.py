"""
GitHub API integration for the Runner Watchdog.

Provides helpers to:
- Fetch the latest runner release version
- List runners registered against a repo / org
- Obtain runner registration tokens
- Delete a runner from GitHub
"""

import logging
from typing import Any
from urllib.parse import urlparse

import requests

from controller.config import GITHUB_TOKEN, REPO_URL

logger = logging.getLogger("watchdog.github")

_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _parse_repo_url() -> tuple[str, str]:
    """Extract (owner, repo) from REPO_URL like https://github.com/org/repo."""
    parts = urlparse(REPO_URL).path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from REPO_URL: {REPO_URL}")
    return parts[0], parts[1]


# ── Version info ─────────────────────────────────────────────────────────────

def get_latest_runner_version() -> str:
    """Return the tag name (e.g. 'v2.329.0') of the newest runner release."""
    url = "https://api.github.com/repos/actions/runner/releases/latest"
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    tag: str = resp.json()["tag_name"]          # e.g. "v2.329.0"
    return tag.lstrip("v")                       # normalize → "2.329.0"


# ── Runner listing ───────────────────────────────────────────────────────────

def get_repo_runners() -> list[dict[str, Any]]:
    """List self-hosted runners registered to the configured repo."""
    owner, repo = _parse_repo_url()
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runners"
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json().get("runners", [])


def get_org_runners(org: str) -> list[dict[str, Any]]:
    """List self-hosted runners registered to an organization."""
    url = f"https://api.github.com/orgs/{org}/actions/runners"
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json().get("runners", [])


# ── Registration / removal ───────────────────────────────────────────────────

def get_runner_registration_token() -> str:
    """Obtain a short-lived registration token for the configured repo."""
    owner, repo = _parse_repo_url()
    url = (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/actions/runners/registration-token"
    )
    resp = requests.post(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()["token"]


def delete_runner(runner_github_id: int) -> None:
    """Remove a runner from GitHub by its numeric runner ID."""
    owner, repo = _parse_repo_url()
    url = (
        f"https://api.github.com/repos/{owner}/{repo}"
        f"/actions/runners/{runner_github_id}"
    )
    resp = requests.delete(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    logger.info("Deleted runner %s from GitHub", runner_github_id)
