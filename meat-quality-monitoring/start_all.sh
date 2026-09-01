#!/bin/bash
# Meat Quality Monitoring System - desktop launcher (systemd-aware)
#
# All servers are managed by systemd and start at boot:
#   meat-monitor-dashboard.service   -> http://localhost:8502 (Streamlit dashboard)
#   pi-camera-feed.service           -> http://localhost:5000 (camera feed)
#   meat-monitor-latest-view.service -> http://localhost:8600 (latest view page)
#
# This script only: 1) makes sure the systemd services are up,
# 2) waits (with hard curl timeouts) until pages answer, 3) opens the pages
# in Chromium. It never starts or kills any server itself, and it explicitly
# exports the graphical-session variables so the browser opens even when the
# launcher context has no DISPLAY/WAYLAND_DISPLAY.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Logging (file + whatever terminal may be attached) --------------------
LOG="$SCRIPT_DIR/start_all.log"
exec > >(tee -a "$LOG") 2>&1
echo ""
echo "$(date '+%Y-%m-%d %H:%M:%S') - launcher started"

# --- Graphical session fallbacks (required to open the browser) -------------
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DISPLAY="${DISPLAY:-:0}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

# --- Locate a browser binary (PATH may be minimal in desktop context) -------
CHROME=""
if command -v chromium >/dev/null 2>&1; then
    CHROME=chromium
elif command -v chromium-browser >/dev/null 2>&1; then
    CHROME=chromium-browser
elif [ -x /usr/lib/chromium/chromium ]; then
    CHROME=/usr/lib/chromium/chromium
fi

echo "=========================================="
echo "Meat Quality Monitoring System"
echo "=========================================="
echo ""

# --- 1. Ensure systemd services are running (start them if stopped) --------
for svc in meat-monitor-dashboard pi-camera-feed meat-monitor-latest-view; do
    if systemctl is-active --quiet "$svc.service" 2>/dev/null; then
        echo "[OK] $svc.service is running"
    else
        echo "[..] $svc.service is not running - starting it..."
        if sudo -n systemctl start "$svc.service" 2>/dev/null; then
            echo "[OK] $svc.service started"
        else
            echo "[!!] Could not start $svc.service (run: sudo systemctl start $svc)"
        fi
    fi
done

# --- 2. Wait for a page to answer, then open it in the browser -------------
open_when_ready() {
    local url="$1" name="$2" tries="${3:-10}"
    local i
    for ((i = 1; i <= tries; i++)); do
        # --max-time guarantees a probe NEVER hangs
        if curl -s -o /dev/null --max-time 2 "$url"; then
            echo "[OK] $name is up: $url"
            open_page "$url"
            return 0
        fi
        sleep 1
    done
    echo "[!!] $name did not answer at $url after ${tries}s - opening anyway."
    open_page "$url"
    return 1
}

open_page() {
    local url="$1"
    if [ -n "$CHROME" ]; then
        # setsid detaches from this script so a closing terminal can't kill it
        setsid "$CHROME" "$url" >/dev/null 2>&1 </dev/null &
        echo "[->] opened in Chromium: $url"
    elif command -v xdg-open >/dev/null 2>&1; then
        setsid xdg-open "$url" >/dev/null 2>&1 </dev/null &
        echo "[->] opened with xdg-open: $url"
    else
        echo "[!!] No browser found - open manually: $url"
    fi
}

echo ""
echo "Opening Latest View page..."
open_when_ready "http://localhost:8600" "Latest View" 10

echo "Opening Dashboard..."
open_when_ready "http://localhost:8502" "Dashboard" 15

echo ""
echo "Pages opened. Services keep running in the background via systemd."
echo "Log: $LOG"

# Give the detached browser processes a moment to fully spawn before this
# script (and its launcher context) goes away.
sleep 3
