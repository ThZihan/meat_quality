#!/bin/bash
# Opens the monitoring pages on the Pi's own display at login.
#
# Runs from ~/.config/autostart via lxsession-xdg-autostart, which the labwc
# session starts (see /etc/xdg/labwc/autostart). Nothing here needs doing by
# hand: after a power cut the services come back through systemd and this
# reopens the pages as soon as they answer.
#
#   http://localhost:8600  Latest View
#   http://localhost:8502  Dashboard
#
# The pages are served by systemd units that are already enabled at boot, so
# this script only waits for them and opens the browser. It never starts or
# stops a service itself.

set -u

LOG="$HOME/.meat-monitor-display.log"
exec >>"$LOG" 2>&1
echo "=== $(date '+%F %T') display autostart ==="

# The autostart context can inherit a minimal environment, and Chromium exits
# immediately if it cannot find the compositor. Fill in the graphical-session
# variables the same way start_all.sh does, without overriding a real session.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export DISPLAY="${DISPLAY:-:0}"

# Streamlit and the latest-view server take a while after boot, and the browser
# showing a connection error is worse than it appearing a few seconds later.
wait_for() {
    local url="$1" name="$2" tries="${3:-60}"
    for ((i = 1; i <= tries; i++)); do
        if curl -s -o /dev/null --max-time 2 "$url"; then
            echo "[OK] $name answered after ${i}s"
            return 0
        fi
        sleep 1
    done
    echo "[!!] $name never answered after ${tries}s; opening anyway"
    return 1
}

CHROME=""
for c in chromium chromium-browser /usr/lib/chromium/chromium; do
    if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then CHROME="$c"; break; fi
done
if [ -z "$CHROME" ]; then
    echo "[!!] No chromium binary found; nothing to open"
    exit 0
fi

# A dedicated profile keeps this window independent of any browsing the user is
# doing, and makes the instance identifiable so a re-run cannot stack windows.
PROFILE="$HOME/.config/meat-monitor-kiosk"

# Confirm the match is really a browser. A bare `pgrep -f` on the profile path
# also matches any shell whose own command line happens to contain it --
# including the one running this script -- which made the guard block every
# launch.
already_open() {
    local pid comm
    for pid in $(pgrep -f -- "--user-data-dir=$PROFILE" 2>/dev/null); do
        [ "$pid" = "$$" ] && continue
        comm=$(cat "/proc/$pid/comm" 2>/dev/null) || continue
        case "$comm" in chrom*) return 0 ;; esac
    done
    return 1
}

if already_open; then
    echo "[--] Display window is already open; leaving it alone"
    exit 0
fi

wait_for "http://localhost:8600" "Latest View" 60
wait_for "http://localhost:8502" "Dashboard"   90

mkdir -p "$PROFILE"
# Both pages as tabs in one window. Add --start-fullscreen (or --kiosk, which
# also removes the toolbar) if this becomes a dedicated display.
setsid "$CHROME" \
    --user-data-dir="$PROFILE" \
    --no-first-run \
    --disable-session-crashed-bubble \
    --start-maximized \
    "http://localhost:8600" \
    "http://localhost:8502" \
    >/dev/null 2>&1 </dev/null &

echo "[->] Opened Latest View (8600) and Dashboard (8502)"
