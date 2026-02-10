#!/bin/bash
# Auto-updating runner for the apartment scraper.
#
# This script:
#   1. Pulls the latest code from Git before starting
#   2. Installs/updates dependencies if requirements.txt changed
#   3. Launches the scraper as a child process
#   4. Periodically checks for new commits on the remote
#   5. If an update is found, gracefully stops the scraper, pulls, and restarts
#
# Usage:
#   ./deploy/auto-update-runner.sh
#
# Environment variables (all optional):
#   UPDATE_CHECK_INTERVAL  - Seconds between Git update checks (default: 300 = 5 min)
#   GIT_REMOTE             - Git remote name (default: origin)
#   GIT_BRANCH             - Git branch to track (default: main)

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="${APP_DIR}/venv"
PYTHON="${VENV_DIR}/bin/python"
PIP="${VENV_DIR}/bin/pip"

UPDATE_CHECK_INTERVAL="${UPDATE_CHECK_INTERVAL:-300}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
GIT_BRANCH="${GIT_BRANCH:-main}"

SCRAPER_PID=""

# ─── Logging helpers ──────────────────────────────────────────────────
log()   { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [runner] $*"; }
warn()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [runner] WARNING: $*" >&2; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [runner] ERROR: $*" >&2; }

# ─── Cleanup on exit ─────────────────────────────────────────────────
cleanup() {
    log "Runner shutting down..."
    stop_scraper
    log "Goodbye!"
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# ─── Stop the running scraper ────────────────────────────────────────
stop_scraper() {
    if [[ -n "${SCRAPER_PID}" ]] && kill -0 "${SCRAPER_PID}" 2>/dev/null; then
        log "Stopping scraper (PID ${SCRAPER_PID})..."
        kill -TERM "${SCRAPER_PID}" 2>/dev/null || true
        # Wait up to 30 seconds for graceful shutdown
        local waited=0
        while kill -0 "${SCRAPER_PID}" 2>/dev/null && [[ ${waited} -lt 30 ]]; do
            sleep 1
            waited=$((waited + 1))
        done
        # Force kill if still running
        if kill -0 "${SCRAPER_PID}" 2>/dev/null; then
            warn "Scraper did not stop gracefully, forcing kill..."
            kill -9 "${SCRAPER_PID}" 2>/dev/null || true
        fi
        wait "${SCRAPER_PID}" 2>/dev/null || true
        SCRAPER_PID=""
        log "Scraper stopped."
    fi
}

# ─── Git pull and dependency install ─────────────────────────────────
pull_and_install() {
    cd "${APP_DIR}"

    # Capture current requirements hash before pull
    local req_hash_before=""
    if [[ -f requirements.txt ]]; then
        req_hash_before=$(md5sum requirements.txt 2>/dev/null | awk '{print $1}' || md5 -q requirements.txt 2>/dev/null || echo "")
    fi

    log "Pulling latest code from ${GIT_REMOTE}/${GIT_BRANCH}..."
    if ! git pull "${GIT_REMOTE}" "${GIT_BRANCH}"; then
        error "git pull failed! Continuing with current code."
        return 1
    fi
    log "Code updated successfully."

    # Check if requirements changed
    local req_hash_after=""
    if [[ -f requirements.txt ]]; then
        req_hash_after=$(md5sum requirements.txt 2>/dev/null | awk '{print $1}' || md5 -q requirements.txt 2>/dev/null || echo "")
    fi

    if [[ "${req_hash_before}" != "${req_hash_after}" ]]; then
        log "requirements.txt changed — installing dependencies..."
        "${PIP}" install --upgrade pip -q
        "${PIP}" install -r requirements.txt -q
        log "Dependencies updated."
    else
        log "requirements.txt unchanged — skipping dependency install."
    fi

    return 0
}

# ─── Start the scraper ────────────────────────────────────────────────
start_scraper() {
    cd "${APP_DIR}"
    log "Starting scraper..."
    "${PYTHON}" -m src.main &
    SCRAPER_PID=$!
    log "Scraper started (PID ${SCRAPER_PID})."
}

# ─── Check if remote has new commits ─────────────────────────────────
check_for_updates() {
    cd "${APP_DIR}"

    # Fetch latest remote refs (quietly)
    if ! git fetch "${GIT_REMOTE}" "${GIT_BRANCH}" --quiet 2>/dev/null; then
        warn "git fetch failed — will retry next cycle."
        return 1
    fi

    local local_hash remote_hash
    local_hash=$(git rev-parse HEAD 2>/dev/null)
    remote_hash=$(git rev-parse "${GIT_REMOTE}/${GIT_BRANCH}" 2>/dev/null)

    if [[ "${local_hash}" != "${remote_hash}" ]]; then
        log "Update detected! Local: ${local_hash:0:8} -> Remote: ${remote_hash:0:8}"
        return 0  # Update available
    fi

    return 1  # No update
}

# ─── Main loop ────────────────────────────────────────────────────────
main() {
    log "=========================================="
    log "  Apartment Scraper — Auto-Update Runner"
    log "=========================================="
    log "App directory:    ${APP_DIR}"
    log "Git remote:       ${GIT_REMOTE}/${GIT_BRANCH}"
    log "Update check:     every ${UPDATE_CHECK_INTERVAL}s"
    log ""

    # Verify venv exists
    if [[ ! -x "${PYTHON}" ]]; then
        error "Python venv not found at ${VENV_DIR}. Run deploy/setup.sh first."
        exit 1
    fi

    # Initial pull and start
    pull_and_install || true
    start_scraper

    # Main update-check loop
    local seconds_waited=0
    while true; do
        sleep 10
        seconds_waited=$((seconds_waited + 10))

        # Check if scraper is still alive
        if ! kill -0 "${SCRAPER_PID}" 2>/dev/null; then
            warn "Scraper process (PID ${SCRAPER_PID}) died unexpectedly!"
            wait "${SCRAPER_PID}" 2>/dev/null || true
            log "Restarting scraper..."
            pull_and_install || true
            start_scraper
            seconds_waited=0
            continue
        fi

        # Time to check for updates?
        if [[ ${seconds_waited} -ge ${UPDATE_CHECK_INTERVAL} ]]; then
            seconds_waited=0
            log "Checking for Git updates..."

            if check_for_updates; then
                log "New version available — restarting with updated code."
                stop_scraper
                pull_and_install || true
                start_scraper
            else
                log "Already up to date."
            fi
        fi
    done
}

main "$@"
