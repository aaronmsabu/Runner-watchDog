# 🐕 Runner Watchdog

**Automated fleet controller for self-hosted GitHub Actions runners.**

Detects upcoming runner version enforcement, tracks runner versions across your fleet, and automatically replaces outdated runners using rolling updates — zero CI downtime.

---

## Architecture

```
                GitHub API
                     │
            Version Monitor Service
                     │
               Runner Registry
                  (Redis)
                     │
              Fleet Controller
                     │
         ┌───────────┴───────────┐
         │                       │
   Runner Provisioner      Runner Remover
         │                       │
      Docker Engine         GitHub Runner API
```

**Three core services:**

| Service              | Description                                                   |
| -------------------- | ------------------------------------------------------------- |
| Version Monitor      | Polls GitHub releases for `actions/runner` to detect upgrades |
| Runner Registry      | Redis-backed store of all managed runner metadata             |
| Fleet Controller     | Orchestrates rolling replacement of outdated runners          |

---

## Quick Start

### 1. Clone & configure

```bash
git clone <your-repo-url> runner-watchdog
cd runner-watchdog
cp .env.example .env
# Edit .env with your GITHUB_TOKEN and REPO_URL
```

### 2. Build the runner image

```bash
docker build \
  --build-arg RUNNER_VERSION=2.329.0 \
  -t github-runner-image:2.329.0 \
  docker/runner-image/
```

### 3. Start the stack

```bash
docker compose up --build
```

This starts:
- **Redis** on port `6379`
- **Controller API** on port `8000`
- **Background watchdog** loop (checks every `CHECK_INTERVAL_SECONDS`)

### 4. Verify

```bash
# Health check
curl http://localhost:8000/health

# Latest runner version
curl http://localhost:8000/version/latest

# Fleet status
curl http://localhost:8000/status
```

---

## API Endpoints

| Method | Path               | Description                              |
| ------ | ------------------ | ---------------------------------------- |
| GET    | `/health`          | Liveness check                           |
| GET    | `/runners`         | List all runners from local registry     |
| GET    | `/runners/github`  | List runners registered on GitHub        |
| GET    | `/version/latest`  | Fetch latest runner version from GitHub  |
| GET    | `/status`          | Fleet summary (counts, upgrade status)   |
| POST   | `/check-update`    | Manually trigger a version check         |
| POST   | `/trigger-update`  | Manually trigger a rolling update        |

---

## Configuration

All settings are controlled via environment variables (`.env` file):

| Variable                 | Default          | Description                              |
| ------------------------ | ---------------- | ---------------------------------------- |
| `GITHUB_TOKEN`           | —                | GitHub PAT (repo, workflow, admin:org)   |
| `REPO_URL`               | —                | Target repo for runner registration      |
| `REDIS_HOST`             | `redis`          | Redis hostname                           |
| `REDIS_PORT`             | `6379`           | Redis port                               |
| `RUNNER_VERSION`         | `2.329.0`        | Current baseline runner version          |
| `RUNNER_IMAGE_NAME`      | `github-runner-image` | Docker image name for runners       |
| `UPDATE_BATCH_PERCENT`   | `10`             | % of fleet to replace per rolling cycle  |
| `CHECK_INTERVAL_SECONDS` | `3600`           | How often the watchdog checks (seconds)  |

---

## Project Structure

```
runner-watchdog/
├── controller/
│   ├── api.py              # FastAPI control API
│   ├── config.py           # Centralized configuration
│   ├── github_api.py       # GitHub API client
│   ├── main.py             # Fleet controller + watchdog loop
│   ├── runner_manager.py   # Provisioning, removal, rolling updates
│   └── version_checker.py  # Version comparison logic
├── database/
│   └── redis_client.py     # Redis runner registry
├── docker/
│   └── runner-image/
│       ├── Dockerfile       # Self-hosted runner image
│       └── start.sh         # Runner entrypoint with cleanup trap
├── Dockerfile               # Controller service image
├── docker-compose.yml       # Full stack orchestration
├── requirements.txt
└── .env.example
```

---

## How Rolling Updates Work

1. Watchdog detects a new runner version on GitHub
2. Identifies all runners in the registry running an older version
3. Calculates batch size (`UPDATE_BATCH_PERCENT` of total fleet)
4. For each batch:
   - Launch a new runner container at the latest version
   - Wait for it to register with GitHub
   - Gracefully stop the old runner (triggers cleanup trap → deregisters from GitHub)
5. Repeat until all runners are upgraded

**Result:** CI pipelines continue running throughout — no outage.

---

## License

MIT
