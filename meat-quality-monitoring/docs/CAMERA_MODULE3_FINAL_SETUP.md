# Camera Module 3 — Final Setup & Debugging Runbook

**Status: FINAL / VERIFIED** — Last verified: 2026-08-27 14:38 (+06)
**Hardware:** Raspberry Pi 5 + Raspberry Pi Camera Module 3 (Sony IMX708, motorized autofocus)
**Purpose of this document:** record the finalized camera architecture, the exact changes made, the verification evidence, and a symptom→fix playbook so future debugging is fast.

---

## 1. Final Architecture (what runs where)

```
                    ┌─────────────────────────────────────────────────┐
                    │  pi-camera-feed.service  (camera_feed.py)       │
                    │  http://0.0.0.0:5000                            │
                    │                                                 │
 browser/LAN  ──────┤  /            viewer page (camera_feed.html)    |
 192.168.10.x:5000  │  /video_feed  MJPEG 800x480 @30fps (rpicam-vid │
                    │                --autofocus-mode continuous)    │
                    │  /status      camera health JSON                │
                    │  /capture     latest low-res frame              │
                    │  /capture_highres  ★ coordinated 4608x2592 AF  │
                    │                still (rpicam-still              │
                    │                --autofocus-on-capture)          │
                    │  GPIO 18 LED ownership (light_detector logic)   │
                    └───────────────────────▲─────────────────────────┘
                                            │ HTTP GET every 30 s
                    ┌───────────────────────┴─────────────────────────┐
                    │  pi-image-capture.service (capture.py)          │
                    │  --interval 30                                  │
                    │  → GET http://127.0.0.1:5000/capture_highres    │
                    │  → save /home/zihan/pending_sync/img_*.jpg      │
                    │  → INSERT row status='pending' in               │
                    │    /home/zihan/sync_state.db  (table: images)   │
                    │  (pi-image-sync.timer later uploads + flips      │
                    │   status — unchanged from before)               │
                    └─────────────────────────────────────────────────┘
```

**Key design decision (the important one):** the timed capture service does
NOT open the camera device itself. Only the feed server owns `/dev/video*`.
Timed captures go through the HTTP endpoint, which serializes access with the
live stream. Two processes racing for the IMX708 was the root cause of every
`Device or resource busy` failure seen during setup.

### Coordination mechanism
- `capture_in_progress` event (camera_feed.py) is set while a high-res still runs.
- All `get_camera_process()` callers block until the event clears — this includes
  a NEW `/video_feed` client that connects mid-capture (the bug fixed at 14:14).
- Concurrent `/capture_highres` requests get HTTP **409 CONFLICT**; the timed
  client retries 409s after 5 s instead of failing.
- The timed client retries `ConnectionRefusedError` for up to 60 s at boot
  (systemd starts both units in parallel; Flask binds port 5000 ~1 s later).

---

## 2. Verified End-State (evidence, 2026-08-27)

| Check | Result |
|---|---|
| Kernel overlay | `dtoverlay=imx708,cam0` active in `/boot/firmware/config.txt` |
| Sensor detection | `rpicam-hello --list-cameras` → `imx708 [4608x2592]` |
| Feed service | `pi-camera-feed.service` enabled+active; `/status` → `ok`, continuous AF |
| Timed service | `pi-image-capture.service` enabled+active, 30 s interval |
| Boot persistence | After reboot both units auto-started at 14:27:42; 9 captures produced |
| Image validity | Every checked capture: JPEG 4608×2592, ~820–900 KB, ledger `pending` |
| Viewer survives capture | Same MJPEG client: 1,505 complete frames across a timed capture |
| Camera races after guard | 0 × `resource busy` / `failed to acquire camera` in final windows |
| GPIO conflicts | 0 × `GPIO busy` from timed client (LED init is lazy/direct-mode only) |
| Ledger sample | `117|img_20260827_143754.jpg|/home/zihan/pending_sync/img_20260827_143754.jpg|2026-08-27 14:37:54|pending` |

---

## 3. Changes Made (chronological, vs. original code)

### 3.1 Boot config — `/boot/firmware/config.txt`
- Was (v2.1 era): `dtoverlay=imx219,cam0`
- **Now:** `dtoverlay=imx708,cam0`  (Module 3)
- `camera_auto_detect=0` stays (explicit overlays).
- Backups kept on the Pi:
  - `/boot/firmware/config.txt.backup-module3` (original imx708)
  - `/boot/firmware/config.txt.backup-camera-v2.1` (imx219 era)

### 3.2 `camera_feed.py` (Module 3 feed server — main live server)
- `build_still_capture_command(..., autofocus_on_capture=True)` for the FINAL
  still: `--autofocus-mode auto --autofocus-on-capture`, and `--immediate`
  removed so autofocus/AWB settle. Preliminary light-probe still uses
  continuous AF + short timeout (unchanged behavior).
- `capture_in_progress` event + `still_capture_lock` added; `get_camera_process()`
  blocks while a still owns the camera (`allow_during_capture=True` only for the
  endpoint's own restart); `generate_frames()` no longer races a mid-capture
  restart; concurrent high-res requests return 409.
- Still command (final): `rpicam-still -t 5000 -o - --width 4608 --height 2592
  --nopreview --quality 95 --encoding jpg --gain 1 --autofocus-mode auto
  --autofocus-range normal --autofocus-speed normal --autofocus-on-capture`

### 3.3 `capture.py` (timed capture service)
- Default mode changed from direct `rpicam-still` to HTTP:
  `CAMERA_CAPTURE_URL=http://127.0.0.1:5000/capture_highres` (env-overridable).
- New `capture_from_feed_server()`: validates HTTP 200 / `image/jpeg` / JPEG
  SOI-EOI markers, atomic write via `.part` file, retries ConnectionRefused
  (boot race) and HTTP 409 (capture overlap).
- `--direct-camera` flag preserves old direct mode for diagnostics;
  `--capture-url ""` also forces direct mode.
- LED controller is now lazy (only initialized in direct-camera mode) —
  eliminates `GPIO busy` noise since the feed server owns GPIO 18.

### 3.4 systemd units (in repo `deploy/` and installed in `/etc/systemd/system/`)
- **NEW** `pi-camera-feed.service` — runs `camera_feed.py`, enabled, `Restart=always`.
- `pi-image-capture.service` — now `Requires=/After=pi-camera-feed.service`,
  sets `CAMERA_CAPTURE_URL` + `CAMERA_CAPTURE_HTTP_TIMEOUT=30`, runs
  `capture.py --interval 30`, enabled.

### 3.5 v2.1 side (kept, unused but restorable)
`camera_config_v2.py`, `camera_feed_v2.py`, `templates/camera_feed_v2.html`,
`start_camera_feed_v2.sh`, sample captures `captures/pi_cam_v2_*.jpg`.

---

## 4. File & Function Map

| Concern | Location |
|---|---|
| Feed server entry | `camera_feed.py` `__main__` (~line 890) |
| Camera process mgmt + capture gate | `camera_feed.py` [`get_camera_process()`](../meat-quality-monitoring/camera_feed.py:276) |
| High-res coordinated endpoint | `camera_feed.py` [`capture_highres_frame()`](../meat-quality-monitoring/camera_feed.py:676) |
| Still command builder | `camera_feed.py` [`build_still_capture_command()`](../meat-quality-monitoring/camera_feed.py:197) |
| MJPEG generator (viewer path) | `camera_feed.py` `generate_frames()` |
| Timed loop / CLI | `capture.py` [`main()`](../meat-quality-monitoring/capture.py:511) |
| HTTP fetch + retries | `capture.py` [`capture_from_feed_server()`](../meat-quality-monitoring/capture.py:218) |
| One iteration (capture+ledger) | `capture.py` [`capture_once()`](../meat-quality-monitoring/capture.py:412) |
| Interval / URL defaults | `capture.py` [`DEFAULT_INTERVAL_SECONDS`](../meat-quality-monitoring/capture.py:59), `DEFAULT_CAPTURE_URL` (line 61) |
| Feed unit | `deploy/pi-camera-feed.service` |
| Timed unit | `deploy/pi-image-capture.service` |

---

## 5. Debugging Playbook (symptom → cause → fix)

### 5.1 "No cameras available!" / sensor not in `rpicam-hello --list-cameras`
- Cause: overlay mismatch. Check: `grep imx /boot/firmware/config.txt`
  and `sudo dmesg | grep -iE 'imx708|imx219|chip id'`
  - `failed to read chip id 708` → a v2.1 is attached but overlay says imx708
  - `failed to read chip id 219 … -121` → Module 3 attached, overlay says imx219
- Fix: set `dtoverlay=imx708,cam0` (Module 3) or `imx219,cam0` (v2.1), then reboot once.
- Rule: overlay must match the physically attached module. It cannot be
  changed at runtime.

### 5.2 `Device or resource busy` / `failed to acquire camera` in feed logs
- Cause: a second process opened the camera (e.g., someone ran
  `rpicam-still`/`capture.py --direct-camera` while the feed was live, or a
  stale orphan process).
- Fix: `pgrep -af 'rpicam|capture.py|camera_feed'` and kill the offender;
  the coordination guard should otherwise make this impossible via HTTP paths.
- Historical note: the 14:14 occurrence was a NEW /video_feed client starting
  during a timed still — fixed by the `capture_in_progress` gate; a 2026-08-27
  post-fix scan showed zero occurrences.

### 5.3 Timed client log: `Connection refused` at boot only
- Cause: both units start in parallel; Flask binds ~1 s later.
- Status: benign since the retry patch — client retries every 2 s for 60 s.
  If seen repeatedly AFTER boot → feed server down: `systemctl status pi-camera-feed`.

### 5.4 Timed client log: `HTTP 409 CONFLICT`
- Cause: previous high-res capture still running (e.g., after a service
  restart overlapped a cycle). Client now retries after 5 s.
- Persistent 409s → check feed log for a hung `rpicam-still`;
  `sudo journalctl -u pi-camera-feed -f` while it happens.

### 5.5 Feed is up but page shows "Failed to load camera feed"
- `curl -s localhost:5000/status` → if `error`, read message.
- Check stream directly: `curl -s --max-time 3 localhost:5000/video_feed -o /tmp/s.mjpeg`
  then verify JPEG frames present (SOI `ff d8`).
- Check `rpicam-vid` child alive: `pgrep -af rpicam-vid`.

### 5.6 Captures stale / no new rows in `sync_state.db`
- `systemctl status pi-image-capture` → active?
- `sudo journalctl -u pi-image-capture -n 50` → last "Captured and recorded"?
- Latest rows: `sqlite3 /home/zihan/sync_state.db "SELECT id,filename,status,capture_time FROM images ORDER BY id DESC LIMIT 5"`
- Manual test (no service interference needed):
  `venv/bin/python3 capture.py --once --pending-dir /tmp/t --db-path /tmp/t.db`

### 5.7 Images are blurry
- Module 3 autofocus needs contrast in the scene. Live view = continuous AF.
  Timed stills force an AF scan (`--autofocus-on-capture`). If still soft:
  check subject distance (AF range `normal` ≈ >10 cm; use `macro` for closer
  via `CAMERA_AUTOFOCUS_RANGE` env for the feed, or adjust
  `camera_config.CameraCaptureConfig.autofocus_range`).

### 5.8 `GPIO busy` warnings
- Expected ONLY if two LED-owning processes run (e.g., manual `camera_feed_v2.py`
  alongside `camera_feed.py`). Normal ops: only the feed service owns GPIO 18.

---

## 6. Operational Commands

```bash
# Services
sudo systemctl restart pi-camera-feed        # restart live feed (port 5000)
sudo systemctl restart pi-image-capture      # restart timed captures
systemctl status pi-camera-feed pi-image-capture

# Live logs
sudo journalctl -u pi-camera-feed -f
sudo journalctl -u pi-image-capture -f

# Health
curl -s localhost:5000/status | python3 -m json.tool
rpicam-hello --list-cameras

# Manual coordinated capture (exactly what the timer does)
curl -s -o /tmp/manual.jpg localhost:5000/capture_highres && file /tmp/manual.jpg

# One-shot timed-client test with isolated ledger
cd ~/projects/meat-quality-monitoring
venv/bin/python3 capture.py --once --pending-dir /tmp/t --db-path /tmp/t.db

# Direct-camera diagnostic mode (bypasses feed server; stop feed first!)
sudo systemctl stop pi-camera-feed
venv/bin/python3 capture.py --once --direct-camera

# Ledger
sqlite3 /home/zihan/sync_state.db "SELECT id,filename,status,capture_time FROM images ORDER BY id DESC LIMIT 10"
```

### Configuration knobs (env vars)
| Var | Default | Effect |
|---|---|---|
| `CAMERA_CAPTURE_URL` | `http://127.0.0.1:5000/capture_highres` | Timed client endpoint; empty → direct mode |
| `CAMERA_CAPTURE_HTTP_TIMEOUT` | `30` | Seconds per coordinated capture |
| `--interval` (unit) | `30` | Seconds between captures |
| `CAMERA_WIDTH/HEIGHT/FRAME_RATE/JPEG_QUALITY` | 800/480/30/85 | Live stream config |
| `CAMERA_AUTOFOCUS_MODE/RANGE/SPEED` | continuous/normal/normal | Feed + still AF tuning |
| `LED_DARK/BRIGHT_THRESHOLD` etc. | see `camera_config.py` | LED assist thresholds |

---

## 7. Rollback / Alternatives

### Back to Camera v2.1 (IMX219, fixed focus)
1. Edit `/boot/firmware/config.txt`: `dtoverlay=imx219,cam0` (or restore
   `/boot/firmware/config.txt.backup-camera-v2.1`)
2. `sudo systemctl disable --now pi-camera-feed pi-image-capture`
3. Reboot once.
4. `./start_camera_feed_v2.sh` (runs `camera_feed_v2.py` on port 5000).
   Note: v2.1 server has no `capture_in_progress` coordination; do not run
   the timed service against it without re-enabling direct mode
   (`CAMERA_CAPTURE_URL=` empty) — v2.1 fixed-focus stills are safe to take
   directly but will conflict with its own live stream if run in parallel.

### Emergency: timed captures blocking the live feed
Set `CAMERA_CAPTURE_URL=` (empty) + `--direct-camera` semantics require the
feed to be stopped; simplest emergency is disabling the timer:
`sudo systemctl stop pi-image-capture` — the live feed is unaffected.

---

## 8. Incident Log (for future archaeology)

| Time (+06) | Event |
|---|---|
| ~13:30 | Camera swapped Module 3 → v2.1; imx708 overlay caused `chip id 708` failure → created v2.1 stack (`*_v2.py`, imx219 overlay) — worked, images blurry due to lens obstruction |
| ~13:52 | Camera swapped back v2.1 → **Module 3 (final)**; restored imx708 overlay |
| 13:55 | `camera_feed.py` live on 5000, IMX708 detected, viewer OK |
| 14:10 | Replaced manual server with `pi-camera-feed.service`; added `pi-camera-feed`/updated `pi-image-capture` units |
| 14:12 | First coordinated production capture (ledger 87) 4608×2592 |
| 14:14 | Found+fixed mid-capture new-viewer race (`Device or resource busy`) → `capture_in_progress` gate |
| 14:17–14:25 | Stress window: viewer kept 1,505 frames across timed capture; 0 races |
| 14:27 | Controlled reboot: both services auto-started; 9 captures validated |
| 14:36 | Hardened client: ConnectionRefused + HTTP 409 retries; lazy LED init |
| 14:38 | Final verification: capture OK, zero ERROR lines. **State = FINAL.** |
